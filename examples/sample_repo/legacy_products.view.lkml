# this view is not included in the existing model
view: legacy_products {
  sql_table_name: public.legacy_products ;;

  dimension: id {
    primary_key: yes
    type: number
    sql: ${TABLE}.id ;;
  }
}
