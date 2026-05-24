import pdfplumber

pdf_path = r'c:/odoo17b2b/b2b/content.pdf'

with pdfplumber.open(pdf_path) as pdf:
    all_text = ''
    for i, page in enumerate(pdf.pages):
        text = page.extract_text()
        print(f'--- PAGE {i+1} ---')
        print(text)
        all_text += f'\n--- PAGE {i+1} ---\n' + (text or '')

with open('content_pdf_text.txt', 'w', encoding='utf-8') as f:
    f.write(all_text)
