import pandas as pd
import boto3
from sqlalchemy import create_engine
import json
from urllib.parse import unquote_plus
import requests
import io
import os
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, to_date, when
from pyspark.sql.functions import udf
from pyspark.sql.types import *
from pyspark.sql.functions import count, mean, sum

DB_ENDPOINT = os.getenv("DB_ENDPOINT")
DB_USER = os.getenv("DB_USER")
DB_PASS = os.getenv("DB_PASS")

connString = f"mysql+pymysql://{DB_USER}:{DB_PASS}@{DB_ENDPOINT}:3306/Wellmark"
engine = create_engine(connString)
s3 = boto3.client("s3")

def lambda_handler(event, context):
    if event:
        file_obj = event["Records"][0]
        bucketname = str(file_obj["s3"]["bucket"]["name"])
        filename = unquote_plus(str(file_obj["s3"]["object"]["key"]))
        print(bucketname, filename)
        if "COVID-19_Case_Surveillance_Public_Use_Data_with_Geography" in filename:
            clean_covid(bucketname, filename)
        if "Indicators_of_Health_Insurance_Coverage_at_the_Time_of_Interview" in filename:
            upload_insurance(bucketname, filename)
    
    return {
        'statusCode': 200,
        'body': json.dumps('Hello from Lambda!')
    }

def clean_covid(bucket, filename):
    obj = s3.get_object(Bucket=bucket, Key=filename)
    spark = SparkSession.builder.appName("CovidCleaner").getOrCreate()
    df = spark.read.option("header", "true").csv(io.BytesIO(obj['Body'].read()))
    df = df.drop("state_fips_code").drop("res_county").drop("county_fips_code")

    #Filtering the months
    df = df.withColumn("case_month", to_date(col("case_month"), "yyyy-MM"))
    df = df.filter(col("case_month").isNotNull())
    #Making all yn columns have proper null values
    yn_vals = ["Yes", "No"]
    yn_cols = ["underlying_conditions_yn", "death_yn", "icu_yn", "hosp_yn", "exposure_yn"]
    for c in yn_cols:
        df = df.withColumn(c, when(col(c).isin(yn_vals), col(c)).otherwise(None))
    #Making symptom sstatus the only two values
    symptom_vals = ["Asymptomatic", "Symptomatic"]
    df = df.withColumn("symptom_status", when(col("symptom_status").isin(symptom_vals), col("symptom_status")).otherwise(None))
    #Making different null values all one null
    miss_vals = ["Unknown", "Missing", "null", "NA"]
    df = df.withColumn("Process", when(col("Process").isin(miss_vals), None).otherwise(col("Process")))
    df = df.withColumn("age_group", when(col("age_group").isin(miss_vals), None).otherwise(col("age_group")))
    df = df.withColumn("ethnicity", when(col("ethnicity").isin(miss_vals), None).otherwise(col("ethnicity")))
    df = df.withColumn("race", when(col("race").isin(miss_vals), None).otherwise(col("race")))
    #Taking these three and making others into other to match up with the race column in the other df
    #Still find a way to fix this
    df = df.withColumn("race", when(col("race").isNull(), "None").otherwise(col("race")))
    main_race_vals = ["Black", "White", "Asian", "None"]
    df = df.withColumn("race", when(col("race").isin(main_race_vals), col("race")).otherwise("Other"))
    #If they are "Hispanic/Latino" in ethnicity, assign that to race
    #Otherwise, take the race val
    hispanic = ["Hispanic/Latino"]
    df = df.withColumn("race", when(col("ethnicity").isin(hispanic), "Hispanic/Latino").otherwise(col("race")))
    df = df.drop("ethnicity")
    df = df.filter(col("current_status").isNotNull())
    sex_vals = ["Male", "Female"]
    df = df.withColumn("sex", when(col("sex").isin(sex_vals), col("sex")).otherwise(None))
    onehot_cols = ["underlying_conditions_yn", "death_yn", "icu_yn", "hosp_yn", "symptom_status", "current_status", "exposure_yn", "Process"]
    df = df.fillna("None", subset=onehot_cols)
    for col in onehot_cols:
        dvs = [row[col].replace(" ", "_") for row in df.select(col).distinct().collect()]
        for val in dvs:
            df = df.withColumn(f"{col}_{val}", when(df[col] == val, 1).otherwise(0))
    df = df.drop(*onehot_cols)
    cols = df.columns
    non_cols = ["case_month", "res_state", "age_group", "sex", "race", "case_onset_interval", "case_positive_specimen_interval"]
    for c in non_cols:
        cols.remove(c)
    sum_agg = [sum(col).alias(f"sum_{col}") for col in cols]
    final_df = df.groupBy("case_month", "res_state", "age_group", "sex", "race").agg(count("*").alias("TotalCases"), 
                                                                          mean("case_positive_specimen_interval").alias("case_positive_specimen_interval_mean"),
                                                                         mean("case_onset_interval").alias("case_onset_interval_mean"),
                                                                         *sum_agg)

    pd_df = final_df.toPandas()
    
    pd_df.to_sql("CovidData", engine, schema="Wellmark", if_exists="replace", index=False)

def upload_insurance(bucket, filename):
    obj = s3.get_object(Bucket=bucket, Key=filename)
    df = pd.read_csv(io.BytesIO(obj['Body'].read()))
    df.to_sql("CovidHealthcareData", engine, schema="Wellmark", if_exists="replace", index=False)
    