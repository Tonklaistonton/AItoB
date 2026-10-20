"""Bounded CSV/XLSX upload processing, in memory; no LLM or fixed-file writes."""
import base64
import binascii
import csv
import hashlib
import io
import posixpath
import re
import zipfile
from decimal import Decimal, InvalidOperation
from xml.etree import ElementTree as ET
from auth import authenticate

MAX_BYTES=1_000_000
MAX_ROWS=1000
HEADER=['expense_id','vendor','amount']
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
REL='{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'

def authorize_upload(authorization):
    identity=authenticate(authorization)
    if identity is None:return 401,{'error':'invalid_key_or_permissions'}
    if identity.get('team')!='Finance' or identity.get('role')!='finance_reader':
        return 403,{'error':'finance_upload_access_denied'}
    return 200,{'authorized':True}

def xml(raw):
    if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():raise ValueError('xml_declarations_not_allowed')
    return ET.fromstring(raw)

def xlsx_rows(raw):
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        infos=z.infolist();names=[i.filename for i in infos]
        if len(infos)>200 or len(set(names))!=len(names) or sum(i.file_size for i in infos)>8_000_000:
            raise ValueError('xlsx_archive_limit')
        if any('..' in n.split('/') or n.startswith('/') or '\\' in n for n in names):raise ValueError('invalid_archive_path')
        if any(n.startswith('xl/externalLinks/') or n.lower().endswith('vbaproject.bin') for n in names):raise ValueError('external_links_or_macros_not_allowed')
        for name in names:
            if name.endswith('.rels'):
                if any(r.get('TargetMode')=='External' for r in xml(z.read(name))):
                    raise ValueError('external_links_not_allowed')
        sheets=xml(z.read('xl/workbook.xml')).findall('s:sheets/s:sheet',NS)
        if len(sheets)!=1:raise ValueError('one_sheet_required')
        rels=xml(z.read('xl/_rels/workbook.xml.rels'))
        targets=[r.get('Target') for r in rels if r.get('Id')==sheets[0].get(REL)]
        if len(targets)!=1 or not targets[0]:raise ValueError('invalid_sheet_relationship')
        target=targets[0]
        member=target.lstrip('/') if target.startswith('/') else posixpath.normpath('xl/'+target)
        if not member.startswith('xl/worksheets/') or member not in names:raise ValueError('invalid_sheet_relationship')
        shared=[]
        if 'xl/sharedStrings.xml' in names:
            for item in xml(z.read('xl/sharedStrings.xml')):
                shared.append(''.join(n.text or '' for n in item.findall('.//s:t',NS)))
        sheet=xml(z.read(member))
        if sheet.find('s:mergeCells',NS) is not None:raise ValueError('merged_cells_not_allowed')
        rows=[];last_row=0
        for row in sheet.findall('s:sheetData/s:row',NS):
            row_id=int(row.get('r','0'))
            if not last_row<row_id<=MAX_ROWS+1:raise ValueError('xlsx_row_limit_or_order')
            if not rows and row_id!=1:raise ValueError('header_must_be_first_row')
            last_row=row_id;values=['','',''];seen=set()
            for cell in row.findall('s:c',NS):
                if cell.find('s:f',NS) is not None:raise ValueError('formulas_not_allowed')
                ref=cell.get('r','');match=re.fullmatch(r'([A-C])([1-9][0-9]*)',ref)
                if not match or int(match[2])!=row_id or ref in seen:raise ValueError('only_columns_A_to_C_supported')
                seen.add(ref);kind=cell.get('t');value=cell.findtext('s:v','',NS)
                if kind=='s':value=shared[int(value)]
                elif kind=='inlineStr':value=''.join(n.text or '' for n in cell.findall('s:is//s:t',NS))
                elif kind not in (None,'n','str'):raise ValueError('unsupported_cell_type')
                values[ord(match[1])-65]=value
            rows.append((row_id,values))
        return rows

def read_upload(raw,filename):
    if not isinstance(filename,str) or not 1<=len(filename)<=120 or any(c in filename for c in '/\\\x00'):
        raise ValueError('invalid_filename')
    ext=filename.rsplit('.',1)[-1].lower()
    if ext=='csv':
        rows=[(n,row) for n,row in enumerate(csv.reader(io.StringIO(raw.decode('utf-8-sig'))),1)]
    elif ext=='xlsx':rows=xlsx_rows(raw)
    else:raise ValueError('csv_or_xlsx_required')
    if not rows or rows[0]!=(1,HEADER):raise ValueError('expected_expense_id_vendor_amount')
    if len(rows)>MAX_ROWS+1:raise ValueError('row_limit')
    return rows[1:]

def clean_rows(rows):
    accepted=[];audit=[];seen={};duplicates=0;total=Decimal('0.00')
    for number,raw in rows:
        if not raw or all(not str(x).strip() for x in raw):continue
        reason=None
        if len(raw)!=3:reason='invalid_fields'
        else:
            expense_id,vendor,raw_amount=[str(x).strip() for x in raw]
            try:
                if len(raw_amount)>40:raise ValueError()
                amount=Decimal(raw_amount)
                if not amount.is_finite() or amount<=0 or amount>Decimal('1000000000') or amount!=amount.quantize(Decimal('0.01')):raise ValueError()
                amount=amount.quantize(Decimal('0.01'))
            except (InvalidOperation,ValueError):reason='invalid_amount'
            if reason is None:
                if not expense_id or not vendor or len(expense_id)>120 or len(vendor)>200:reason='invalid_fields'
                elif any(v.lstrip().startswith(('=','+','-','@')) or any(ord(c)<32 for c in v) for v in (expense_id,vendor)):reason='unsafe_spreadsheet_text'
                elif expense_id in seen:
                    if seen[expense_id]==(vendor,amount):reason='duplicate';duplicates+=1
                    else:reason='conflicting_expense_id'
                else:
                    seen[expense_id]=(vendor,amount)
                    accepted.append([expense_id,vendor,format(amount,'.2f')]);total+=amount
        audit.append([number,'accepted' if reason is None else reason])
    summary={'input_rows':len(audit),'cleaned_rows':len(accepted),'duplicate_rows':duplicates,
             'rejected_rows':len(audit)-len(accepted)-duplicates,'total_amount':format(total,'.2f'),'currency':'THB'}
    return accepted,audit,summary

def csv_export(header,rows,filename):
    stream=io.StringIO(newline='');writer=csv.writer(stream);writer.writerow(header);writer.writerows(rows)
    text=stream.getvalue()
    return {'filename':filename,'content':text,'sha256':hashlib.sha256(text.encode('utf8')).hexdigest()}

def process_for_key(authorization,arguments):
    # Must also be called by Handler before body parsing for unauthorized callers.
    status,result=authorize_upload(authorization)
    if status!=200:return status,result
    if not isinstance(arguments,dict) or set(arguments)!={'filename','content_base64'}:
        return 400,{'error':'invalid_upload_arguments'}
    encoded=arguments['content_base64']
    if not isinstance(encoded,str) or len(encoded)>1_333_336:return 413,{'error':'upload_too_large'}
    try:
        raw=base64.b64decode(encoded,validate=True)
        if len(raw)>MAX_BYTES:return 413,{'error':'upload_too_large'}
        rows=read_upload(raw,arguments['filename'])
        accepted,audit,summary=clean_rows(rows)
        return 200,{'summary':summary,'input_sha256':hashlib.sha256(raw).hexdigest(),
                    'cleaned':csv_export(HEADER,accepted,'expenses_uploaded_cleaned.csv'),
                    'audit':csv_export(['source_row','status'],audit,'expenses_uploaded_audit.csv')}
    except ValueError as exc:
        known={'xml_declarations_not_allowed','xlsx_archive_limit','invalid_archive_path','external_links_or_macros_not_allowed','external_links_not_allowed','one_sheet_required','invalid_sheet_relationship','merged_cells_not_allowed','xlsx_row_limit_or_order','header_must_be_first_row','formulas_not_allowed','only_columns_A_to_C_supported','unsupported_cell_type','invalid_filename','csv_or_xlsx_required','expected_expense_id_vendor_amount','row_limit'}
        error=str(exc) if str(exc) in known else 'invalid_upload_file'
        return 422,{'error':error}
    except (binascii.Error,UnicodeError,csv.Error,zipfile.BadZipFile,ET.ParseError,KeyError,IndexError,RuntimeError,NotImplementedError):
        return 422,{'error':'invalid_upload_file'}
