view: inventory_locations {
  sql_table_name: public.inventory_locations ;;

  # this view label will override the defined join name at the exploration level
  label: "Inventory Locations"

  dimension: id {
    type: number
    primary_key: yes
    sql: ${TABLE}.id ;;
  }
}
