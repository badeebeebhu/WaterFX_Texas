import pandas as pd

def basic_setup():
  import geopandas as gpd
  import plotly.graph_objects as go
  import requests
  import sys

  pws_gdf = gpd.read_file("data/PWS_shapefile/PWS_Export.shp")
  colonias_gdf = gpd.read_file("data/Colonia_shapefile/COLONIAS_COMMUNITIES.shp")

  if pws_gdf.crs is None or colonias_gdf.crs is None:
      raise ValueError("One of the shapefiles is missing a CRS. Please ensure all shapefiles have a valid CRS.")
  if pws_gdf.crs != colonias_gdf.crs:
      colonias_gdf = colonias_gdf.to_crs(pws_gdf.crs)
  joined = gpd.sjoin(colonias_gdf, pws_gdf, how="inner", predicate="intersects")
  colonias_by_pws = (
      joined.groupby(['PWSId', 'pwsName'])
      .agg({
          'NAME': list,
      })
      .reset_index()
  )

  blocks_gdf = gpd.read_file("data/tl_2024_48_tract/tl_2024_48_tract.shp")
  if pws_gdf.crs is None or blocks_gdf.crs is None:
      raise ValueError("One of the shapefiles is missing a CRS. Please ensure all shapefiles have a valid CRS.")
  if pws_gdf.crs != blocks_gdf.crs:
      blocks_gdf = blocks_gdf.to_crs(pws_gdf.crs)
  blocks_gdf['orig_area'] = blocks_gdf.geometry.area

  intersection = gpd.overlay(blocks_gdf, pws_gdf, how='intersection')
  intersection['intersection_area'] = intersection.geometry.area
  intersection = intersection.merge(
      blocks_gdf[['GEOID', 'orig_area']],
      on='GEOID',
      how='left'
  )

  intersection['percent_overlap'] = intersection['intersection_area'] / intersection['orig_area_x']
  weighted_blocks_by_pws = intersection[['PWSId', 'pwsName', 'GEOID', 'percent_overlap']]
  blocks_grouped = (
      weighted_blocks_by_pws
        .groupby(['PWSId', 'pwsName'])[['GEOID', 'percent_overlap']]
        .agg(list)
        .reset_index()
  )

  pws_gdf = pws_gdf.to_crs(epsg=4326)
  blocks_gdf = blocks_gdf.to_crs(epsg=4326)

  blocks_gdf['state'] = blocks_gdf['GEOID'].str[:2]
  blocks_gdf['county'] = blocks_gdf['GEOID'].str[2:5]
  blocks_gdf['tract'] = blocks_gdf['GEOID'].str[5:11]
  blocks_gdf['blkgrp'] = blocks_gdf['GEOID'].str[11:]

  variables = {
      'B01003_001E': 'total_pop',
      'B19013_001E': 'amhi',
      'B23025_005E': 'unemp_count',
      'B25010_001E': 'avg_household_size',
      'B17001_002E': 'poverty_count'
  }

  endpoint = "https://api.census.gov/data/2021/acs/acs5"
  params = {
      "get": ",".join(variables.keys()),
      "for": "tract:*",
      "in":  "state:48 county:*",
      "key": "b7ea71552392058e92b8d3f73cd42534e595ac19"
  }
  response = requests.get(endpoint, params=params)
  data = response.json()
  census_df = pd.DataFrame(data[1:], columns=data[0])
  census_df = census_df.rename(columns=variables)
  for col in variables.values():
      census_df[col] = pd.to_numeric(census_df[col], errors='coerce')
  census_df.loc[census_df['amhi'] < 0, 'amhi'] = pd.NA
  census_df['poverty_rate'] = (
      census_df['poverty_count'] / census_df['total_pop'])
  census_df=census_df.fillna(0)

  census_df['GEOID'] = (
      census_df['state']
    + census_df['county']
    + census_df['tract']
  )
  census_df= census_df.set_index('GEOID')[['total_pop', 'unemp_count', 'poverty_rate','amhi', 'avg_household_size']]

  return colonias_by_pws, blocks_gdf, census_df, pws_gdf, blocks_grouped

def draw_pws_blocks(pws_id, pws_gdf,blocks_gdf):
    import plotly.graph_objects as go
    import geopandas as gpd
    selected_pws = pws_gdf[pws_gdf['PWSId'] == pws_id]
    blocks_in_pws = gpd.overlay(blocks_gdf, selected_pws, how='intersection').reset_index(drop=True)
    minx, miny, maxx, maxy = selected_pws.total_bounds
    lon_center, lat_center = (minx + maxx) / 2, (miny + maxy) / 2

    fig = go.Figure()

    fig.add_trace(go.Choroplethmapbox(
        geojson=selected_pws.__geo_interface__,
        locations=selected_pws.index.astype(str),
        z=[1] * len(selected_pws),
        colorscale=[[0, 'rgba(0,0,0,0)'], [1, 'rgba(0,0,0,0)']],
        showscale=False,
        marker_line_color="red",
        marker_line_width=2,
        marker_opacity=1,
        hoverinfo='none'
    ))

    fig.add_trace(go.Choroplethmapbox(
        geojson=blocks_in_pws.__geo_interface__,
        locations=blocks_in_pws.index.astype(str),
        z=blocks_in_pws.index,
        colorscale="Viridis",
        showscale=False,
        marker_opacity=0.6,
        marker_line_width=0.5,
        hoverinfo='text',
        hovertext=blocks_in_pws['GEOID']
    ))


    fig.update_layout(
        mapbox_style="open-street-map",
        mapbox_zoom=10,
        mapbox_center={"lat": lat_center, "lon": lon_center},
        margin={"r":0, "t":0, "l":0, "b":0}
    )

    return fig

def system_setup():
    # This function is a placeholder for any system setup required before running the script.
    # No code is needed here for standard Python scripts.
    pass

def get_dww_url(pwsId):
    system_setup()
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/114.0.5735.198 Safari/537.36"
    )
    driver = webdriver.Chrome(options=chrome_options)

    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    import time
    import json
    import re
    number = "number=" + pwsId
    name = "name=" + ""
    activity   = "ActivityStatusCD=All"
    county  = "county=All"
    waterSys = "WaterSystemType=All"
    sourceType = "SourceWaterType=All"
    sampleType = "SampleType=none"
    action = "action=Search+For+Water+Systems"
    join="&"

    BASE = "https://dww2.tceq.texas.gov/"
    SEARCH = f"{BASE}/DWW/JSP/SearchDispatch?"
    url = f"{SEARCH}{number}{join}{action}"

    driver.get(url)
    water_system_links = []
    tables = driver.find_elements(By.TAG_NAME, "table")
    main_table = None
    for table in tables:
        if "Water System Name" in table.text:
            main_table = table
            break
    if main_table:
        rows = main_table.find_elements(By.TAG_NAME, "tr")
        for i, row in enumerate(rows):
            cells = row.find_elements(By.TAG_NAME, "td")
    url2 = None
    if main_table:
      for i in range(1, min(6, len(rows))):
          try:
              row = rows[i]
              cells = row.find_elements(By.TAG_NAME, "td")
              if len(cells) >= 2:
                  name_cell = cells[1]
                  links = name_cell.find_elements(By.TAG_NAME, "a")
                  if links:
                      name = links[0].text.strip()
                      url = links[0].get_attribute("href")
                      if name and url:
                          water_system_links.append((name, url))
                  sys_cell = cells[0]
                  links = sys_cell.find_elements(By.TAG_NAME, "a")
                  if links:
                      sys = links[0].text.strip()
                      url2 = links[0].get_attribute("href")
                      if sys and url2:
                          print(f"Found water system: {sys} {url2}")
          except Exception as e:
              print(f"Error processing row {i}: {e}")
    driver.quit()
    return url, url2

def scrape_fact_page(pwsid, url, url2):
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/114.0.5735.198 Safari/537.36"
    )
    driver = webdriver.Chrome(options=chrome_options)
    driver2 = webdriver.Chrome(options=chrome_options)
    driver.get(url)
    driver2.get(url2)

    wait = WebDriverWait(driver, 10)
    wait.until(EC.presence_of_element_located((By.TAG_NAME, "table")))


    # Entities CSV
    labels = [
    ("PWSID",             "Water System No."),
    ("System name",       "System Name"),
    ("System type",       "Federal Type"),
    ("Owner type",        "Federal Source"),
    ("County",            "Principal County Served"),
    ("Population served", "Population Served"),
]
    def get_entity_value(driver, label_text):
      try:
        xpath = (
            f"//td[.//font[contains(normalize-space(.), '{label_text}')]]"
            "/following-sibling::td[1]"
        )
        el = driver.find_element(By.XPATH, xpath)
        return el.text.strip()
      except Exception:
        return None

    entity = {"pwsid": pwsid}
    for col_name, html_label in labels:
       entity[col_name] = get_entity_value(driver, html_label)

    # Add scraping for Water System Contacts
    try:
        contacts_table = driver.find_element(
            By.XPATH,"//table[./tbody/tr[1]/th[contains(normalize-space(.), 'Water System Contacts')]]"
        )
        ac_row = contacts_table.find_element(
            By.XPATH,
            ".//tbody/tr[td[1][contains(normalize-space(.), 'Administrative Contact')]]"
        )
        info_cell  = ac_row.find_element(By.XPATH, ".//td[2]")
        info_text  = info_cell.text.strip().replace('\u00a0', ' ')

        raw_phone_cell = ac_row.find_element(By.XPATH, ".//td[3]")

        business_phone = raw_phone_cell.find_element(
            By.XPATH,
            ".//table//tr[td[1][contains(normalize-space(.),'BUS')]]/td[2]"
        ).text.strip().replace('\u00a0', ' ')

        entity["Contact Info"] = info_text
        entity["Phone"] = business_phone
    except Exception as e:
        print("Couldn't scrape : Water System Contacts", e)
        entity["Contact Info"] = entity["Phone"] = None

    try:
      ao_table = driver.find_element(
          By.XPATH, "//table[.//tr[1]/th[contains(normalize-space(.), 'Annual Operating Period')]]"
      )
      pop_td = ao_table.find_element(
          By.XPATH,".//tbody/tr[3]/td[6]"
      )
      population = pop_td.text.strip().replace('\u00a0', '')
      entity["Population served"] = population

    except Exception as e:
      entity["Population served"] = None

    try:
      sc_table = driver.find_element(
          By.XPATH,"//table[./tbody/tr[1]/th[contains(normalize-space(.), 'Service Connection')]]"
      )
      sc_cells = sc_table.find_elements(
          By.XPATH,".//tbody/tr[3]/td"
      )
      sc_values = [td.text.strip().replace('\u00a0', '') for td in sc_cells]
      entity["SC Type"], entity["SC Count"], entity["SC Meter Type"], entity["SC Meter Size"] = sc_values

    except Exception as e:
      entity["SC Type"] = entity["SC Count"] = entity["SC Meter Type"] = entity["SC Meter Size"] = None

    df_ent = pd.DataFrame([entity])


    # Facilities CSV
    try:
      production_mgd = "Not Available"
      avg_daily = "Not Available"
      max_daily = "Not Available"
      pprm_table = driver2.find_element(
      By.XPATH, "//th[contains(normalize-space(.), 'WS Flow Rates')]/ancestor::table"
      )
      for row in pprm_table.find_elements(By.XPATH, ".//tr[position()>2]"):
          cells = row.find_elements(By.TAG_NAME, "td")
          label = cells[0].text.strip()
          if "Provided Production Capacity" in label:
              production_mgd = cells[1].text.strip()
              break
      for row in pprm_table.find_elements(By.XPATH, ".//tr[position()>2]"):
          cells = row.find_elements(By.TAG_NAME, "td")
          label = cells[0].text.strip()
          if "Daily Demand" in label:
              max_daily = cells[1].text.strip()
              break
      for row in pprm_table.find_elements(By.XPATH, ".//tr[position()>2]"):
          cells = row.find_elements(By.TAG_NAME, "td")
          label = cells[0].text.strip()
          if "Average Daily" in label:
              avg_daily = cells[1].text.strip()
              break
    except Exception as e:
        pass


    try:
      storage_cap = "Not Available"
      meas_table = driver2.find_element(
      By.XPATH,"//th[contains(normalize-space(.), 'WS Measures')]/ancestor::table"
      )
      for row in meas_table.find_elements(By.XPATH, ".//tr[position()>2]"):
          cells = row.find_elements(By.TAG_NAME, "td")
          label = cells[0].text.strip()
          if "Storage Capacity" in label and "Elevated" not in label:
              storage_cap = cells[1].text.strip() + " " + cells[2].text.strip()
              break
    except Exception as e:
        pass


    try:
      fac_table = driver.find_element(
          By.XPATH,"//table[./tbody/tr[1]/th[contains(normalize-space(.), 'Water System Facilities')]]"
      )
      data_rows = fac_table.find_elements(By.XPATH, ".//tbody/tr[position()>2]")
      facility_data = []
      for row in data_rows:
          cells = row.find_elements(By.TAG_NAME, "td")

          if len(cells) < 3:
              continue

          fac_id = cells[0].text.strip()
          parts = cells[2].text.split('-')  # note: this is an en dash on the site
          fac_type   = parts[0].strip() if len(parts) > 0 else ""
          fac_status = parts[1].strip() if len(parts) > 1 else ""

          facility_data.append({
              "facility_id":     fac_id,
              "facility_type":   fac_type,
              "facility_status": fac_status,
              "production_mgd" : production_mgd,
              "storage_cap"     : storage_cap,
              "avg_daily"     :avg_daily,
              "max_daily"     :max_daily
          })
    except Exception as e:
      facility_data.append({
              "facility_id":     None,
              "facility_type":   None,
              "facility_status": None,
              "production_mgd" : production_mgd,
              "storage_cap"     : storage_cap,
              "avg_daily"     :avg_daily,
              "max_daily"     :max_daily
          })


    df_fac = pd.DataFrame(facility_data)

    # Individual Violations CSV
    try:
      indv_violations_table = driver.find_element(
          By.XPATH,"//table[./tbody/tr[1]/th[contains(normalize-space(.), 'Individual Violations')]]"
      )
      data_rows = indv_violations_table.find_elements(By.XPATH, ".//tbody/tr[position()>2]")
      indv_violations_data = []
      for row in data_rows:
          cells = row.find_elements(By.TAG_NAME, "td")
          viol_no = cells[0].text.strip() if len(cells) > 0 else ''
          date = cells[1].text.strip() if len(cells) > 1 else ''
          violation = cells[3].text.strip() if len(cells) > 3 else ''
          contaminant = cells[5].text.strip() if len(cells) > 5 else ''
          indv_violations_data.append({
                  "Violation No.":     viol_no,
                  "Date":   date,
                  "Violation": violation,
                  "Contaminant": contaminant
          })
    except Exception as e:
      indv_violations_data.append({
                  "Violation No.":     None,
                  "Date":   None,
                  "Violation": None,
                  "Contaminant": None,
          })

    df_indv_viol = pd.DataFrame(indv_violations_data)


    # Individual Violations CSV
    try:
      grp_violations_table = driver.find_element(
          By.XPATH,"//table[./tbody/tr[1]/th[contains(normalize-space(.), 'Group Violations')]]"
      )
      data_rows = grp_violations_table.find_elements(By.XPATH, ".//tbody/tr[position()>2]")
      grp_violations_data = []
      for row in data_rows:
          cells = row.find_elements(By.TAG_NAME, "td")
          if len(cells) < 2:
              continue
          viol_no = cells[0].text.strip()
          date = cells[1].text.strip()
          violation = cells[3].text.strip() if len(cells) > 3 else ''
          contaminant = cells[5].text.strip() if len(cells) > 5 else ''
          grp_violations_data.append({
                  "Violation No.":     viol_no,
                  "Date":   date,
                  "Violation": violation,
                  "Contaminant": contaminant,
          })
    except Exception as e:
        grp_violations_data.append({
                  "Violation No.":     None,
                  "Date":   None,
                  "Violation": None,
                  "Contaminant": None,
          })

    df_grp_viol = pd.DataFrame(grp_violations_data)

    return df_ent, df_fac, df_grp_viol, df_indv_viol

def fetch_records(name):
    import requests
    import urllib.parse
    base_url = "https://data.epa.gov/efservice"
    table    = "sdwis.sdw_county_served"
    fmt      = "json"
    sort     = "pwsid/asc"
    words = [w for w in name.split() if w]
    if not words:
        return []
    filters = []
    for w in words:
        pattern = f"@{w}@"
        encoded = urllib.parse.quote(pattern, safe='@')
        filters.append(f"pwsname/like/{encoded}")
    path = "/".join(filters)
    url  = f"{base_url}/{table}/{path}/{fmt}"

    resp = requests.get(url)
    resp.raise_for_status()
    return resp.json()

def main():
    # TEMPORARY HARDCODED TEST CASE
    colonias_by_pws, blocks_gdf, census_df, pws_gdf, blocks_grouped = basic_setup()
    sample_name = "CITY OF LYFORD"
    records = fetch_records(sample_name)
    if not records:
        return
    chosen = records[0]
    pwsId = chosen.get('pwsid') or chosen.get('PWSId')
    print(f"\nSystem Overview for PWS ID {pwsId}:")
    print(f"Name: {chosen.get('pwsname', chosen.get('PWSName'))}")
    try:
        names_list = colonias_by_pws.loc[colonias_by_pws['PWSId'] == pwsId,'NAME'].iloc[0]
        print("Colonias served:", ", ".join(names_list))
    except Exception as e:
        print(f"No Colonias served or error: {e}")

    # Get DWW URLs
    url, url2 = get_dww_url(pwsId)
    print(f"Fact sheet URL: {url}")
    print(f"Water system URL: {url2}")

    # Scrape fact page
    df_ent, df_fac, df_grp_viol, df_indv_viol = scrape_fact_page(pwsId, url, url2)
    print("\nEntity:")
    print(df_ent if not df_ent.empty else "No entity data.")
    print("\nFacilities:")
    print(df_fac if not df_fac.empty else "No facility data.")
    print("\nGroup Violations:")
    print(df_grp_viol)
    print("\nIndividual Violations:")
    print(df_indv_viol)

    # Map (just confirm creation)
    try:
        fig = draw_pws_blocks(pwsId, pws_gdf, blocks_gdf)
        print("Map figure created.")
    except Exception as e:
        print(f"Could not create map: {e}")

    return

if __name__ == '__main__':
    main()
