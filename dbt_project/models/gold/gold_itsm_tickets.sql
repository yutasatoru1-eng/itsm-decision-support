/*
    gold_itsm_tickets.sql
    -----------------------
    ETAPE 3 : creation des variables pour le Machine Learning (couche Gold).

    Ce modele part de silver.silver_itsm_tickets (donnees propres) et ajoute
    tout ce dont un modele de prediction a besoin :

      1) Des durees reelles, en minutes (au lieu de deux dates separees)
      2) Des variables temporelles (heure, jour, mois de creation)
      3) La marge SLA (Expected - Actual), gardee a titre informatif
      4) La longueur de la description (utile plus tard pour le NLP)
      5) LA VARIABLE CIBLE : long_resolution_flag

    Pourquoi cette cible et pas "depassement SLA" ?
    --------------------------------------------------
    On a verifie plus tot que dans ce dataset, AUCUN ticket ne depasse jamais
    son SLA (marge toujours >= 0). Une cible sans variance ne peut pas etre
    apprise par un modele. On suit donc la meme demarche que dans le rapport
    de reference : on remplace "depassement SLA" par "risque de resolution
    longue" (long MTTR), qui lui a une vraie variance dans les donnees.

    Definition retenue : un ticket est marque "resolution longue" (1) si
    sa duree de resolution reelle depasse le 75e percentile de l'ensemble
    des tickets. Sinon (0). Ce seuil est calcule automatiquement sur les
    donnees, pas fixe a la main.
*/

with base as (

    select * from {{ ref('silver_itsm_tickets') }}

),

with_durations as (

    select
        *,

        -- Durees reelles, en minutes
        extract(epoch from (first_response_time - created_time)) / 60
            as first_response_minutes,
        extract(epoch from (resolution_time - created_time)) / 60
            as resolution_minutes,
        extract(epoch from (close_time - created_time)) / 60
            as close_minutes,

        -- Bruit deterministe (+/- 60 min), seede sur ticket_id : simule la variabilite
        -- reelle (charge de travail, complexite imprevue) absente du dataset synthetique.
        -- Sans ce bruit, priority determine resolution_minutes de facon quasi parfaite
        -- (ecart-type ~6 min), ce qui rend toute prediction triviale (score parfait).
        (hashtext(ticket_id) % 121 - 60)::float as noise_minutes,

        -- Marge SLA : temps restant avant la limite (peut etre negatif si depasse)
        extract(epoch from (expected_sla_to_first_response - first_response_time)) / 60
            as sla_margin_first_response_min,
        extract(epoch from (expected_sla_to_resolve - resolution_time)) / 60
            as sla_margin_resolution_min,

        -- Variables temporelles utiles pour reperer des tendances (charge par heure, jour...)
        extract(hour from created_time)          as created_hour,
        to_char(created_time, 'Day')             as created_dayofweek,
        to_char(created_time, 'Month')           as created_month,
        date(created_time)                       as created_date,

        -- Longueur de la description : un proxy simple de complexite du ticket,
        -- utile plus tard pour le module NLP
        length(incident_description)             as description_length,

        -- Fenetre SLA (minutes) : utilisee par le moteur de decision (urgence)
        extract(epoch from (expected_sla_to_resolve - created_time)) / 60
            as sla_window_minutes

    from base

),

with_realistic_duration as (

    select
        *,
        greatest(resolution_minutes + noise_minutes, 5) as resolution_minutes_realistic

    from with_durations

),

percentile_calc as (

    select
        percentile_cont(0.75) within group (order by resolution_minutes_realistic)
            as resolution_p75_threshold
    from with_realistic_duration
    where resolution_minutes_realistic is not null

),

with_target as (

    select
        w.*,
        p.resolution_p75_threshold

    from with_realistic_duration w
    cross join percentile_calc p
    where w.resolution_minutes_realistic is not null

)

select
    ticket_id,
    status,
    priority,
    priority_rank,
    source,
    topic,
    agent_group,
    product_group,

    created_time,
    created_date,
    created_hour,
    trim(created_dayofweek)  as created_dayofweek,
    trim(created_month)      as created_month,

    first_response_minutes,
    resolution_minutes,
    resolution_minutes_realistic,
    close_minutes,

    sla_margin_first_response_min,
    sla_margin_resolution_min,

    description_length,
    has_solution,
    sla_window_minutes,

    resolution_p75_threshold,

    -- LA CIBLE : basee sur la duree "realiste" (avec bruit), pas la duree brute
    case
        when resolution_minutes_realistic >= resolution_p75_threshold then 1
        else 0
    end as long_resolution_flag

from with_target
