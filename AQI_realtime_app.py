# Import python packages
import streamlit as st
import pandas as pd
from decimal import Decimal

import snowflake.connector
from snowflake.snowpark import Session
from snowflake.snowpark.context import get_active_session


# Connect using credentials stored in Streamlit secrets

# ----------------
conn = snowflake.connector.connect(
    user=st.secrets["snowflake"]["user"],
    password=st.secrets["snowflake"]["password"],
    account=st.secrets["snowflake"]["account"],
    warehouse=st.secrets["snowflake"]["warehouse"],
    database=st.secrets["snowflake"]["database"],
    schema=st.secrets["snowflake"]["schema"]
)

cur = conn.cursor()
cur.execute("SELECT CURRENT_VERSION()")
version = cur.fetchone()
st.write("Connected to Snowflake, version:", version)

# ----------------

# Get Session
# Create a Snowflake session
session = Session.builder.configs({
    "account": st.secrets["snowflake"]["account"],
    "user": st.secrets["snowflake"]["user"],
    "password": st.secrets["snowflake"]["password"],
    "role": st.secrets["snowflake"]["role"],
    "warehouse": st.secrets["snowflake"]["warehouse"],
    "database": st.secrets["snowflake"]["database"],
    "schema": st.secrets["snowflake"]["schema"]
}).create()

# Page Title
st.title("Real Time Air Quality - At Station Level")
st.write("This streamlit app hosted on Snowflake ❄️ made by Parth F") 
            
state_option,city_option, station_option, date_option  = '','','',''
state_query = """
    select state from aqi.CONSUMPTION.LOCATION_DIM 
    group by state 
    order by 1
"""
state_list = session.sql(state_query).collect()
state_option = st.selectbox('Select State',state_list)

#check the selection
if (state_option is not None and len(state_option) > 1):
    city_query = f"""
    select city from aqi.CONSUMPTION.location_dim 
    where 
    state = '{state_option}' group by city
    order by 1 desc
    """
    city_list = session.sql(city_query).collect()
    city_option = st.selectbox('Select City',city_list)

if (city_option is not None and len(city_option) > 1):
    station_query = f"""
    select station from aqi.CONSUMPTION.location_dim 
        where 
            state = '{state_option}' and
            city = '{city_option}'
        group by station
        order by 1 desc;
    """
    station_list = session.sql(station_query).collect()
    station_option = st.selectbox('Select Station',station_list)

if (station_option is not None and len(station_option) > 1):
    date_query = f"""
    select date(measurement_time) as measurement_date from aqi.CONSUMPTION.date_dim
        group by 1 
        order by 1 desc;
    """
    date_list = session.sql(date_query).collect()
    date_option = st.selectbox('Select Date',date_list)


if (date_option is not None):
    trend_sql = f"""
    select 
        hour(measurement_time) as Hour,
        l.state,
        l.city,
        l.station,
        l.latitude::number(10,7) as latitude,
        l.longitude::number(10,7) as longitude,
        pm25_avg,
        pm10_avg,
        so2_avg,
        no2_avg,
        nh3_avg,
        co_avg,
        o3_avg,
        prominent_pollutant,
        AQI
    from 
        aqi.CONSUMPTION.aqi_fact f 
        join 
        aqi.CONSUMPTION.date_dim d on d.date_pk  = f.date_fk and date(measurement_time) = '{date_option}'
        join 
        aqi.CONSUMPTION.location_dim l on l.location_pk  = f.location_fk and 
        l.state = '{state_option}' and
        l.city = '{city_option}' and 
        l.station = '{station_option}'
    order by measurement_time
    """
    sf_df = session.sql(trend_sql).collect()

    df = pd.DataFrame(sf_df,columns=['Hour','state','city','station','lat', 'lon','PM2.5','PM10','SO3','CO','NO2','NH3','O3','PROMINENT_POLLUTANT','AQI'])
    
    df_aqi = df.drop(['state','city','station','lat', 'lon','PM2.5','PM10','SO3','CO','NO2','NH3','O3','PROMINENT_POLLUTANT'], axis=1)
    df_table = df.drop(['state','city','station','lat', 'lon','PROMINENT_POLLUTANT','AQI'], axis=1)
    df_map = df.drop(['Hour','state','city','station','PM2.5','PM10','SO3','CO','NO2','NH3','O3','PROMINENT_POLLUTANT'], axis=1)
    df_stat = df.drop(['state','city','station','lat', 'lon'], axis=1)
    
    def get_aqi_color(aqi):
        if aqi <= 50:
            return "#00B150" 
        elif aqi <= 100:
            return "#96CD5D" 
        elif aqi <= 150:
            return "#FFFF00"  
        elif aqi <= 200:
            return "#FFBF00" 
        elif aqi <= 250:
            return "#FF0000" 
        elif aqi <= 400:
            return "#771A83" 
        else:
            return "#96CD5D" 

    st.subheader(f"{station_option}, - AQI : {df_stat['AQI'].iloc[-1]}")
    columns_to_convert = ['lat', 'lon']
    df_map[columns_to_convert] = df_map[columns_to_convert].astype(float)
    df_map['color'] = df_map['AQI'].apply(get_aqi_color)
    st.map(df_map, zoom=13, size='AQI',color='color')
    
    st.subheader(f"Hourly AQI Levels")
    st.line_chart(df_aqi,x="Hour", color = '#FFA500', height=250)

    st.subheader(f"Stacked Chart:  Hourly Individual Pollutant Level")
    st.bar_chart(df_table,x="Hour")
    df_stat = df_stat.rename(columns={'PROMINENT_POLLUTANT': 'PROMINENT'})
    st.dataframe(df_stat.iloc[::-1], hide_index=True, height=123, column_order=['Hour','PM2.5','PM10','SO3','CO','NO2','NH3','O3','PROMINENT','AQI'])

    st.subheader(f"Line Chart: Hourly Pollutant Levels")
    st.line_chart(df_table,x="Hour")  
   
    # sql statement
    sql_stmt = """
    select l.latitude, l.longitude,f.aqi
            from 
            aqi.consumption.aqi_fact f
            join aqi.consumption.location_dim l on l.location_pk = f.location_fk
        where 
        date_fk = (select date_pk from aqi.consumption.date_dim
        order by measurement_time desc 
        limit 1 )
    """

    # create a data frame
    sf_df = session.sql(sql_stmt).collect()
    
    pd_df =pd.DataFrame(
            sf_df,
            columns=['lat','lon','AQI'])

    columns_to_convert = ['lat', 'lon']
    pd_df[columns_to_convert] = pd_df[columns_to_convert].astype(float)
    pd_df['color'] = pd_df['AQI'].apply(get_aqi_color)
    
    st.subheader(f"Stations All Over India")
    st.map(pd_df,zoom=4 ,size='AQI',color='color')
    st.image("Indian_aqi_scale.png", caption="Indian Air Quality Scale", use_container_width=True)
