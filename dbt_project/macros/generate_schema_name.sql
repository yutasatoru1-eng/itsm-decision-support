{#
    Par defaut, dbt prefixe les schemas personnalises avec le schema cible
    (ex: "public_silver" au lieu de "silver"). Ce macro annule ce comportement
    pour que nos modeles aillent exactement dans le schema qu'on demande
    (silver, gold), comme dans l'architecture du rapport de reference.
#}
{% macro generate_schema_name(custom_schema_name, node) -%}
    {%- set default_schema = target.schema -%}
    {%- if custom_schema_name is none -%}
        {{ default_schema }}
    {%- else -%}
        {{ custom_schema_name | trim }}
    {%- endif -%}
{%- endmacro %}
