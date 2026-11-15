"""Rebuild the synthetic financial files. Run with reportlab 4.5.1 and openpyxl 3.1.5."""

from datetime import datetime, timezone
from hashlib import sha256
from io import BytesIO
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

import json
import re
from openpyxl import Workbook
from openpyxl.styles import Font
from reportlab.lib.colors import HexColor
from reportlab.pdfgen.canvas import Canvas


ROOT = Path(__file__).resolve().parent / "static" / "samples" / "insights"
WORD = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
CONTENT = "http://schemas.openxmlformats.org/package/2006/content-types"
REL = "http://schemas.openxmlformats.org/package/2006/relationships"
OFFICE = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


def zip_bytes(entries):
    buffer = BytesIO()
    with ZipFile(buffer, "w", ZIP_DEFLATED) as archive:
        for name, data in sorted(entries.items()):
            entry = ZipInfo(name, date_time=(2000, 1, 1, 0, 0, 0))
            entry.compress_type = ZIP_DEFLATED
            archive.writestr(entry, data)
    return buffer.getvalue()


def workbook_bytes(sheets):
    book = Workbook()
    book.remove(book.active)
    book.properties.creator = "AgentForge Sentinel"
    for name, rows in sheets:
        sheet = book.create_sheet(name)
        for row in rows:
            sheet.append(row)
        sheet.freeze_panes = "A2"
        for cell in sheet[1]:
            cell.font = Font(bold=True, color="173C38")
        for column in "ABCDE":
            sheet.column_dimensions[column].width = 24
    stream = BytesIO()
    book.save(stream)
    with ZipFile(stream) as archive:
        parts = {name: archive.read(name) for name in archive.namelist()}
    from xml.etree.ElementTree import fromstring, tostring
    metadata = fromstring(parts["docProps/core.xml"])
    for child in metadata:
        if child.tag.rsplit("}", 1)[-1] in {"created", "modified"}:
            child.text = datetime(2000, 1, 1, tzinfo=timezone.utc).isoformat().replace("+00:00", "Z")
    parts["docProps/core.xml"] = tostring(metadata)
    return zip_bytes(parts)


def docx_bytes(lines):
    def p(text):
        return "<w:p><w:r><w:t>" + escape(text) + "</w:t></w:r></w:p>"

    # Put financial label/value fields in a Word table to exercise the table adapter.
    heading, *fields = lines
    rows = []
    for line in fields:
        label, found, value = line.partition(": ")
        cells = (label + ":", value) if found else (label,)
        rows.append("<w:tr>" + "".join("<w:tc>" + p(cell) + "</w:tc>" for cell in cells) + "</w:tr>")
    table = ('<w:tbl><w:tblPr><w:tblBorders><w:bottom w:val="single" w:sz="4"/>'
             '</w:tblBorders></w:tblPr><w:tblGrid><w:gridCol w:w="4000"/>'
             '<w:gridCol w:w="4800"/></w:tblGrid>' + "".join(rows) + "</w:tbl>")
    return zip_bytes({
        "[Content_Types].xml": f'<Types xmlns="{CONTENT}"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>',
        "_rels/.rels": f'<Relationships xmlns="{REL}"><Relationship Id="rId1" Type="{OFFICE}/officeDocument" Target="word/document.xml"/></Relationships>',
        "word/document.xml": f'<w:document xmlns:w="{WORD}"><w:body>{p(heading)}{table}{p("Synthetic training record. No real payment details.")}<w:sectPr><w:pgSz w:w="12240" w:h="15840"/><w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr></w:body></w:document>',
    })


def pdf_bytes(title, pages):
    stream = BytesIO()
    pdf = Canvas(stream, pagesize=(612, 792), invariant=True, pageCompression=1)
    pdf.setTitle(title)
    for index, lines in enumerate(pages, 1):
        pdf.setFillColor(HexColor("#173c38"))
        pdf.rect(0, 685, 612, 107, fill=1, stroke=0)
        pdf.setFillColor(HexColor("#ffffff"))
        pdf.setFont("Helvetica-Bold", 19)
        pdf.drawString(52, 728, title if index == 1 else "")
        if index == 1 and "Synthetic example" not in lines:
            pdf.setFont("Helvetica", 11)
            pdf.drawString(52, 706, "Synthetic training document")
        # Keep the reading order and coordinates stable across ReportLab runs.
        pdf.setFillColor(HexColor("#233731"))
        text = pdf.beginText(52, 650)
        text.setFont("Helvetica", 11)
        text.setLeading(23)
        for line in lines:
            text.textLine(line)
        pdf.drawText(text)
        pdf.setFont("Helvetica", 9)
        pdf.drawString(52, 40, f"Page {index} of {len(pages)}")
        pdf.showPage()
    pdf.save()
    return stream.getvalue()


def record(role, ref, *lines):
    return [f"Record type: {role}", f"Record ID: {ref}", "Vendor ID: NORTHWIND-LAB",
            "Currency: USD", *lines]


def sheets_for(lines):
    return [("Record", [[*line.split(": ", 1)] for line in lines])]


def collect():
    files = {}
    for flagged in (True, False):
        suffix = "review" if flagged else "control"
        close = "900.00" if flagged else "1300.00"
        files[f"statement-{suffix}.pdf"] = pdf_bytes("Bank statement", [
            ["Synthetic example", "Account: DEMO-CHECKING", "Period: 2026-09-01 to 2026-09-30", "Currency: USD",
             "Opening balance: 1,000.00", "Total deposits: 500.00", "Total withdrawals: 200.00",
             f"Closing balance: {close}", "Date Description Credit Debit Balance",
             "2026-09-02 Subscription refund 200.00 0.00 1200.00",
             "2026-09-03 Contractor payment 0.00 120.00 1080.00"],
            ["Date Description Credit Debit Balance", "2026-09-05 Customer settlement 300.00 0.00 1380.00",
             f"2026-09-07 Hosting and support 0.00 80.00 {close}", "End transactions"],
        ])
        quantity = 4
        printed = 680 if flagged else 480
        invoice_lines = ["Synthetic example", "Description Units Unit Cost Extended Amount",
                         f"Replacement assemblies {quantity} USD 120.00 USD {printed}.00",
                         "Shipping crates 2 USD 40.00 USD 80.00", f"Subtotal: USD {printed + 80}.00",
                         "Discount: USD 20.00", "Shipping: USD 30.00", "Tax: USD 15.00",
                         f"Total due: USD {printed + 105 + (10 if flagged else 0)}.00"]
        files[f"invoice-{suffix}.pdf"] = pdf_bytes("Invoice INV-MATH-41", [invoice_lines, [
            "Terms", "Buyer: Orchard Lab", "Payment due in 30 days", "Packing and shipping listed on page 1.",
        ]])
        rate = "120.00" if flagged else "100.00"
        qty = "200" if flagged else "150"
        files[f"match-invoice-{suffix}.docx"] = docx_bytes(["Invoice INV-410", *record("Invoice", "INV-410",
            "Purchase order: PO-220", f"Item VALVE-KIT: {qty} ea {rate}",
            f"Total due: {'24000.00' if flagged else '15000.00'}",
            f"Payment destination: {'DEMO-SECONDARY' if flagged else 'DEMO-APPROVED'}")])
        related = record("Invoice", "INV-410" if flagged else "INV-411", "Purchase order: PO-220",
                         "Total due: 15000.00", "Item VALVE-KIT: 150 ea 100.00")
        files[f"duplicate-{suffix}.xlsx"] = workbook_bytes(sheets_for(related))
        files[f"policy-{suffix}.pdf"] = pdf_bytes("Related invoices", [record("Invoice", "INV-502",
            f"Group reference: {'INSTALL-Q2' if flagged else 'INSTALL-Q3'}", "Invoice date: 2026-10-02",
            "Total due: 4995.00")])
        files[f"settlement-{suffix}.xlsx"] = workbook_bytes(sheets_for(record("Payment record", "PAY-303",
            "Invoice reference: INV-900", f"Amount: {'410.00' if flagged else '390.00'}")))
        tracked = [["Account", "DEMO-RESERVE"], ["Period", "2026-09"],
                   ["Currency", "EUR"], ["Opening balance", 1000], ["Total credits", 125],
                   ["Total debits", 125], ["Closing balance", "=1000+125-125" if flagged else 1000]]
        ledger = [["Currency", "Amount"], ["USD", 450], ["USD", -200], ["EUR", 90],
                  ["Currency", "Amount"], ["EUR", -35], ["USD", "=50*50"], ["USD", None], ["USD", 0]]
        files[f"ledger-{suffix}.xlsx"] = workbook_bytes([("Summary", tracked), ("Ledger", ledger)])
        files[f"ambiguous-{suffix}.docx"] = docx_bytes(["Statement", "Account: DEMO-B-01", "Period: 2026-09",
            "Currency: EUR", "Number format: decimal comma", "Opening balance: 1.234,50",
            "Total credits: 1,50", "Total debits: 0,00", "Closing balance: 1.236,00",
            *(["Closing balance: 1.237,00"] if flagged else [])])
    files["purchase-order.xlsx"] = workbook_bytes(sheets_for(record("Purchase order", "PO-220",
        "Item VALVE-KIT: 200 ea 100.00")))
    files["delivery.pdf"] = pdf_bytes("Delivery receipt DN-334", [record("Delivery receipt", "DN-334",
        "Purchase order: PO-220", "Item VALVE-KIT: 150 ea")])
    files["trusted-baseline.docx"] = docx_bytes(["Vendor baseline", *record("Vendor baseline", "PROFILE-1",
        "Payment destination: DEMO-APPROVED")])
    files["settlement-invoice.pdf"] = pdf_bytes("Invoice INV-900", [record("Invoice", "INV-900",
        "Total due: 1000.00")])
    files["settlement-first.pdf"] = pdf_bytes("Payment PAY-301", [record("Payment record", "PAY-301",
        "Invoice reference: INV-900", "Amount: 600.00")])
    files["settlement-credit.docx"] = docx_bytes(["Credit note", *record("Credit note", "CREDIT-3",
        "Invoice reference: INV-900", "Amount: 50.00")])
    files["settlement-reversal.pdf"] = pdf_bytes("Reversal REV-301", [record("Payment reversal", "REV-301",
        "Invoice reference: INV-900", "Reverses payment: PAY-301", "Amount: 40.00")])
    files["policy-first.docx"] = docx_bytes(["Invoice INV-501", *record("Invoice", "INV-501",
        "Group reference: INSTALL-Q2", "Invoice date: 2026-10-01", "Total due: 4995.00")])
    return files


if __name__ == "__main__":
    ROOT.mkdir(parents=True, exist_ok=True)
    manifest = {"provenance": "AgentForge Sentinel synthetic training documents", "files": {}}
    for name, data in sorted(collect().items()):
        (ROOT / name).write_bytes(data)
        info = {"bytes": len(data), "sha256": sha256(data).hexdigest()}
        if name.endswith(".pdf"):
            info["pages"] = len(re.findall(rb"/Type /Page\b", data))
        manifest["files"][name] = info
    (ROOT / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
