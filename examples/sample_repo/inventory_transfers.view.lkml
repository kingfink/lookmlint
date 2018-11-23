view: inventory_transfers {
  sql_table_name: public.inventory_transfers ;;

  dimension: id {
    primary_key: yes
    type: number
    sql: ${TABLE}.id ;;
  }

  dimension: source_location_id {
    type: number
    sql: ${TABLE}.source_location_id ;;
  }

  dimension: destination_location_id {
    type: number
    sql: ${TABLE}.destination_location_id ;;
  }
}
