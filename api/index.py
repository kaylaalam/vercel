import io
import gzip
from flask import Flask, request, render_template, send_file, flash, redirect, jsonify
import pandas as pd
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a secure key in production

# Maximum file size (4MB to be safe)
MAX_FILE_SIZE = 4 * 1024 * 1024  # 4MB in bytes

# Mapping dictionary for Reach Location to Store Codes
store_codes = {
    'Altamonte': '002',
    'Apopka Hunt Club': '007',
    'Arden': '049',
    'Auburndale, FL': '043',
    'Beaumont/Wildwood': '042',
    'Bellefontaine, OH': '071',
    'Brookhaven, MS': '048',
    'Brooksville': '035',
    'Cape Coral': '072',
    'Camden': '058',
    'Catering - Cooper City': '055', 
    'Catering - Englewood OH': '026',
    'Catering - Marysville': '047',
    'Catering - Ozark, MO': '052',
    'Centerville - Far Hills, OH': '050',
    'Circleville, OH': '066',
    'Championsgate FL': '008',
    'Cooper City': '055',
    'Coral Springs': '013',
    'Covington': '051',
    'Dacula': '030',
    'Daytona Beach FL': '009',
    'Downtown Orlando (new)': '031',
    'Dr. Phillips': '003',
    'Englewood': '026',
    'Flowery Branch': '039',
    'Flowood': '064',
    'Gainesville': '032',
    'Goose Creek': '054',
    'Greenville': '028',
    'Greenwood, SC': '069',
    'Hinesville': '033',
    'Jacksonville Beach FL': '019',
    'Jacksonville Mandarin': '024',
    'Kingsport': '023',
    'Lady Lake FL': '014',
    'Lake Mary': '004',
    'Lake Nona': '059',
    'Loganville': '010',
    'Longwood, FL': '067',
    'Marysville': '047',
    'McComb': '015',
    'Milledgeville': '017',
    'Millenia': '005',
    'Miramar': '041',
    'Monroe': '068',
    'Montgomery': '021',
    'Morehead, KY': '060',
    'Morgantown, WV': '056',
    'Morristown': '046',
    'N. Lauderdale': '036',
    'North Charleston': '040',
    'Oakland Park': '025',
    'Oakwood': '018',
    'Ocoee': '011',
    'Odessa, FL - Starkey Ranch': '045',
    'Ormond Beach': '034',
    'Oviedo FL': '006',
    'Ozark, MO': '052',
    'Pearl': '022',
    'Pinellas Park FL': '020',
    'Port St. Lucie': '037',
    'Prattville': '053',
    'Springfield, MO': '044',
    'St. Augustine': '029',
    'Statesboro, GA': '062',
    'Sunrise': '012',
    'Tallahassee': '070',
    'Valdosta': '016',
    'Warner Robins': '038',
    'West Boca, FL': '061',
    'Winter Garden': '027',
    'Winter Springs FL': '001',
    'Worthington, OH': '063',
    'Yulee FL': '065',
    'Las Vegas': 'NA'
}

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        start_date_str = request.form.get('start_date')
        end_date_str = request.form.get('end_date')
        uploaded_file = request.files.get('file')

        if not uploaded_file:
            flash('No file uploaded.')
            return redirect(request.url)

        # Check file size
        uploaded_file.seek(0, 2)  # Seek to end of file
        file_size = uploaded_file.tell()  # Get current position (file size)
        uploaded_file.seek(0)  # Reset to beginning of file

        if file_size > MAX_FILE_SIZE:
            flash(f'File size too large. Maximum allowed size is {MAX_FILE_SIZE/1024/1024:.1f}MB')
            return redirect(request.url)

        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d')
        except ValueError:
            flash('Invalid date format. Please use YYYY-MM-DD.')
            return redirect(request.url)

        try:
            # Read the file
            if uploaded_file.filename.lower().endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)

            # Process the data
            df = df[['Email Address', 'Email Opt In', 'Account Created Date', 'Reach Location']]
            df["Account Created Date"] = pd.to_datetime(df["Account Created Date"])
            df = df[(df["Account Created Date"] >= start_date) & (df["Account Created Date"] <= end_date)]
            df = df[df["Email Opt In"].astype(str).str.upper() == "TRUE"]

            df["Reach Location"] = df["Reach Location"].apply(
                lambda x: "Ghost Location" if pd.isna(x) or str(x).strip() in ["", "-"] else str(x).strip()
            )

            df["Store Codes"] = df["Reach Location"].apply(
                lambda x: "057" if x == "Ghost Location" else store_codes.get(x, "")
            )

            df = df.drop(columns=["Email Opt In"])

            # Create Excel file in memory
            output = io.BytesIO()
            
            with pd.ExcelWriter(output, engine='xlsxwriter', mode='wb', options={'constant_memory': True}) as writer:
                df.to_excel(writer, index=False, sheet_name='Sheet1')
                workbook = writer.book
                worksheet = writer.sheets['Sheet1']
                date_format = workbook.add_format({'num_format': 'm/d/yy'})
                date_col_idx = df.columns.get_loc("Account Created Date")

                def colnum_to_excel_col(n):
                    letters = ""
                    n += 1
                    while n:
                        n, remainder = divmod(n-1, 26)
                        letters = chr(65 + remainder) + letters
                    return letters

                date_col_letter = colnum_to_excel_col(date_col_idx)
                worksheet.set_column(f'{date_col_letter}:{date_col_letter}', 12, date_format)

            output.seek(0)
            
            # Check if the output size is too large
            output_size = output.getbuffer().nbytes
            if output_size > MAX_FILE_SIZE:
                flash(f'Processed file size ({output_size/1024/1024:.1f}MB) exceeds the maximum allowed size of {MAX_FILE_SIZE/1024/1024:.1f}MB. Please process fewer records.')
                return redirect(request.url)

            # Compress the output if it's large
            if output_size > MAX_FILE_SIZE / 2:  # If file is larger than 2MB
                compressed_output = io.BytesIO()
                with gzip.GzipFile(fileobj=compressed_output, mode='wb') as gz:
                    gz.write(output.getvalue())
                compressed_output.seek(0)
                return send_file(
                    compressed_output,
                    download_name="processed_file.xlsx",
                    as_attachment=True,
                    mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    headers={"Content-Encoding": "gzip"}
                )
            
            return send_file(
                output,
                download_name="processed_file.xlsx",
                as_attachment=True,
                mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )

        except Exception as e:
            flash(f"Error processing file: {str(e)}")
            return redirect(request.url)

    return render_template('index.html')

# Required for Vercel serverless deployment
def app_handler(request):
    """Handle requests in a serverless environment."""
    return app

# Make the application callable
app.debug = True
application = app 