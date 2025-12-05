from flask import Flask, render_template, request, redirect, url_for, session
import logic
import plotly.io as pio
import plotly
import os
import pandas as pd
import math

app = Flask(__name__)
app.secret_key = os.environ.get('FLASK_SECRET_KEY', 'supersecretkey')  # Needed for session
app.config['PERMANENT_SESSION_LIFETIME'] = 86400  # 1 day

# --- Add this filter for 3 significant figures, plain notation ---
def sigfig_plain(value, sig=3):
    try:
        value = float(value)
        if value == 0:
            return "0"
        # Determine the order of magnitude
        order = int(math.floor(math.log10(abs(value))))
        # Calculate the factor to round to 3 sig figs
        factor = 10 ** (order - sig + 1)
        rounded = round(value / factor) * factor
        # Format as int if possible, else as float with no scientific notation
        if abs(rounded) >= 1:
            s = '{:,.0f}'.format(rounded) if rounded == int(rounded) else '{:,.{prec}f}'.format(rounded, prec=max(0, sig-1-order))
        else:
            s = '{:,.{prec}g}'.format(rounded, prec=sig)
        return s
    except Exception:
        return value

app.jinja_env.filters['sigfig_plain'] = sigfig_plain
# --- End filter ---

@app.before_request
def make_session_permanent():
    session.permanent = True

# Home page: search form
@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        pwsname = request.form.get('pwsname', '').strip()
        if not pwsname:
            return render_template('index.html', error="Please enter a PWS name.")
        return redirect(url_for('select', pwsname=pwsname))
    return render_template('index.html')

# Show matching PWS options
@app.route('/select', methods=['GET', 'POST'])
def select():
    pwsname = request.args.get('pwsname', '').strip()
    matches = logic.fetch_records(pwsname)
    if not matches:
        return render_template('select.html', pwsname=pwsname, matches=[], error="No matches found.")
    if request.method == 'POST':
        pwsid = request.form.get('pwsid')
        rec = next((m for m in matches if m.get('pwsid') == pwsid or m.get('PWSId') == pwsid), None)
        if rec:
            session['selected_pws'] = rec
            print("DEBUG: select route - session['selected_pws'] set:", session['selected_pws'])
            return redirect(url_for('details', pwsid=pwsid))
        else:
            print("DEBUG: select route - record not found for pwsid:", pwsid)
            return render_template('select.html', pwsname=pwsname, matches=matches, error="Selected PWS not found.")
    return render_template('select.html', pwsname=pwsname, matches=matches)

# Show details for selected PWS
@app.route('/details/<pwsid>')
def details(pwsid):
    rec = session.get('selected_pws')
    if not rec or (rec.get('pwsid') != pwsid and rec.get('PWSId') != pwsid):
        print("DEBUG: details route - PWS not found or session expired.")
        return render_template('details.html', error="PWS not found or session expired. Please search again.")
    # Use the selected pwsid for all further data
    pwsid_actual = rec.get('pwsid') or rec.get('PWSId')
    colonias_by_pws, blocks_gdf, census_df, pws_gdf, blocks_grouped = logic.basic_setup()
    # Overview info
    try:
        colonias = colonias_by_pws.loc[colonias_by_pws["PWSId"] == pwsid_actual, "NAME"].iloc[0]
    except Exception as e:
        print("DEBUG: details route - error getting colonias:", e)
        colonias = []
    # Scrape and metrics
    try:
        url, url2 = logic.get_dww_url(pwsid_actual)
        print("DEBUG: url:", url)
        print("DEBUG: url2:", url2)
        df_ent, df_fac, df_gv, df_iv = logic.scrape_fact_page(pwsid_actual, url, url2)
    except Exception as e:
        print("DEBUG: details route - error scraping fact page:", e)
        df_ent = df_fac = df_gv = df_iv = None
        url = url2 = None  # Ensure both are defined
    # Extract entity info smartly
    entity_info = {}
    contact_info = {}
    service_conn = {}
    if df_ent is not None and not df_ent.empty:
        ent = df_ent.iloc[0].to_dict()
        entity_info = {('PWSID' if k == 'PWSID' else k): ent[k] for k in ["System name", "PWSID", "System type", "Owner type", "County"] if k in ent}
        contact_info = {k: ent[k] for k in ["Contact Info", "Phone"] if k in ent}
        for k in ["Population served", "SC Type", "SC Count", "SC Meter Type"]:
            if k in ent:
                new_key = k.replace('SC', 'Connections')
                service_conn[new_key] = ent[k]
    # Metrics as dict, round to 3 decimal places
    def round_3(x):
        try:
            return round(float(x), 3)
        except Exception:
            return x
    def calc_weighted_metrics(row):
        geoids  = row['GEOID']
        weights = row['percent_overlap']
        metrics = census_df.loc[geoids]
        weighted = metrics.multiply(weights, axis=0)
        return weighted.sum() / sum(weights)
    def get_metrics(pwsId, blocks_grouped):
        metrics = blocks_grouped.apply(calc_weighted_metrics, axis=1, result_type='expand')
        blocks_grouped = pd.concat([blocks_grouped, metrics], axis=1)
        blocks_grouped = blocks_grouped.set_index("PWSId")[['amhi', 'total_pop', 'unemp_count', 'poverty_rate', 'avg_household_size']]
        return blocks_grouped.loc[pwsId]
    try:
        metrics = get_metrics(pwsid_actual, blocks_grouped)
    except Exception as e:
        print("DEBUG: details route - error getting metrics:", e)
        metrics = None
    metrics_dict = {k: round_3(v) for k, v in metrics.to_dict().items()} if metrics is not None else {}
    # Fix amhi if negative or not a valid positive number
    amhi = metrics_dict.get('amhi')
    try:
        if amhi is not None and float(amhi) < 0:
            metrics_dict['amhi'] = None
    except Exception:
        metrics_dict['amhi'] = None
    # Calculate average monthly water and sewer flow per household
    avg_household_size = metrics_dict.get('avg_household_size')
    try:
        if avg_household_size is not None and float(avg_household_size) < 0:
            metrics_dict['avg_household_size'] = None
    except Exception:
        metrics_dict['avg_household_size'] = None
    avg_household_size = metrics_dict.get('avg_household_size')
    if avg_household_size is not None:
        try:
            avg_household_size = float(avg_household_size)
            water_flow_per_household = round(2325 * avg_household_size, 2)
            sewer_flow_per_household = round(1279 * avg_household_size, 2)
        except Exception:
            water_flow_per_household = sewer_flow_per_household = None
    else:
        water_flow_per_household = sewer_flow_per_household = None
    # Facilities as list of dicts, and unified metrics
    facility_metrics = {}
    facilities_grouped = []
    if df_fac is not None and not df_fac.empty:
        # Extract unified metrics from the first row (all rows have the same values)
        first = df_fac.iloc[0]
        facility_metrics = {
            'Production (MGD)': first.get('production_mgd'),
            'Storage Cap.': first.get('storage_cap'),
            'Avg Daily': first.get('avg_daily'),
            'Max Daily': first.get('max_daily'),
        }
        # Group facilities by type
        grouped = {}
        for row in df_fac.to_dict(orient='records'):
            ftype = row.get('facility_type', 'Other') or 'Other'
            if ftype not in grouped:
                grouped[ftype] = []
            grouped[ftype].append({'facility_id': row.get('facility_id'), 'facility_status': row.get('facility_status')})
        facilities_grouped = [
            {'type': t, 'count': len(facs), 'facilities': facs}
            for t, facs in grouped.items()
        ]
    # Group/Individual Violations as list of dicts
    group_viol_list = df_gv.to_dict(orient='records') if df_gv is not None else []
    indiv_viol_list = df_iv.to_dict(orient='records') if df_iv is not None else []
    try:
        fig = logic.draw_pws_blocks(pwsid_actual, pws_gdf, blocks_gdf)
        map_html = pio.to_html(fig, full_html=False)
    except Exception as e:
        print("DEBUG: details route - error drawing map:", e)
        map_html = None
    return render_template(
        'details.html',
        rec=rec,
        colonias_served=colonias,
        entity_info=entity_info,
        contact_info=contact_info,
        service_conn=service_conn,
        metrics=metrics_dict,
        facilities_grouped=facilities_grouped,
        facility_metrics=facility_metrics,
        group_viol=group_viol_list,
        indiv_viol=indiv_viol_list,
        map_html=map_html,
        water_flow_per_household=water_flow_per_household,
        sewer_flow_per_household=sewer_flow_per_household,
        url=url,
        url2=url2
    )

if __name__ == '__main__':
    app.run(debug=True)