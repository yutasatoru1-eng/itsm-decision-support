/*
    silver_itsm_tickets.sql
    ------------------------
    ETAPE 2 : nettoyage des donnees (couche Silver).

    Ce modele part de bronze.itsm_tickets_raw (donnees brutes, tout en texte,
    non modifiees) et produit une version propre :
      - espaces superflus retires
      - valeurs vides transformees en vrai NULL (au lieu de chaines vides)
      - dates transformees de texte vers un vrai type TIMESTAMP
      - une ligne par ticket_id (protection anti-doublon)
      - Priority transforme aussi en version numerique ordonnee (priority_rank)
        pour faciliter les futurs tris/graphiques

    C'est l'equivalent SQL exact de ce qu'on avait fait avec pandas dans le
    notebook ITSM_Dataset_Organized.ipynb, mais cette fois le nettoyage vit
    dans la base de donnees et peut etre re-execute a tout moment avec `dbt run`.
*/

with source as (

    select * from {{ source('bronze', 'itsm_tickets_raw') }}

),

cleaned as (

    select
        nullif(trim(ticket_id), '')            as ticket_id,
        nullif(trim(status), '')                as status,
        nullif(trim(priority), '')              as priority,
        nullif(trim(source), '')                as source,
        nullif(trim(topic), '')                 as topic,
        nullif(trim(agent_group), '')           as agent_group,
        nullif(trim(product_group), '')         as product_group,

        -- Conversion des dates : texte "04/07/2024 12:42" -> vrai TIMESTAMP
        to_timestamp(nullif(trim(created_time), ''), 'DD/MM/YYYY HH24:MI')
            as created_time,
        to_timestamp(nullif(trim(expected_sla_to_resolve), ''), 'DD/MM/YYYY HH24:MI')
            as expected_sla_to_resolve,
        to_timestamp(nullif(trim(expected_sla_to_first_response), ''), 'DD/MM/YYYY HH24:MI')
            as expected_sla_to_first_response,
        to_timestamp(nullif(trim(first_response_time), ''), 'DD/MM/YYYY HH24:MI')
            as first_response_time,
        to_timestamp(nullif(trim(resolution_time), ''), 'DD/MM/YYYY HH24:MI')
            as resolution_time,
        to_timestamp(nullif(trim(close_time), ''), 'DD/MM/YYYY HH24:MI')
            as close_time,

        nullif(trim(incident_description), '') as incident_description,
        nullif(trim(solution_used), '')         as solution_used,

        -- Version numerique ordonnee de la priorite (utile pour trier/filtrer)
        case trim(priority)
            when 'Low'      then 1
            when 'Medium'   then 2
            when 'High'     then 3
            when 'Critical' then 4
            else null
        end as priority_rank,

        -- On garde une trace : est-ce que ce ticket a une solution renseignee ?
        (nullif(trim(solution_used), '') is not null) as has_solution

    from source

),

deduplicated as (

    select *,
        row_number() over (partition by ticket_id order by ticket_id) as row_num
    from cleaned
    where ticket_id is not null

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
    expected_sla_to_resolve,
    expected_sla_to_first_response,
    first_response_time,
    resolution_time,
    close_time,
    incident_description,
    solution_used,
    has_solution
from deduplicated
where row_num = 1
