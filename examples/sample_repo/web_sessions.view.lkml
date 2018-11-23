# this view is not included in the only model in this project
view: web_sessions {
  sql_table_name: public.web_sessions ;;

  dimension: id {
    primary_key: yes
    type: number
    sql: ${TABLE}.id ;;
  }
}
