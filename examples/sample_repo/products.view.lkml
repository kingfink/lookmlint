view: products {

  # derived sql contains semicolon, and will throw error at query time
  derived_table: {
    sql:
      select *
      from public.products
      where is_current is true;
      ;;
  }

  dimension: id {
    primary_key: yes
    sql: ${TABLE}.id ;;
  }
}
