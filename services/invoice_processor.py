import pdfplumber
import io
import re


def process_multialarm(pdf_bytes: bytes):

    full_text = ""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                full_text += "\n" + page_text

    invoice_number = re.search(r"Számla száma:\s*(\d+)", full_text)
    invoice_date = re.search(r"Számla kelte:\s*([\d\.]+)", full_text)
    performance_date = re.search(r"Teljesítési dátum:\s*([\d\.]+)", full_text)
    payment_due = re.search(r"Fizetési határidő:\s*([\d\.]+)", full_text)

    header_info = {
        "invoice_number": invoice_number.group(1) if invoice_number else "",
        "invoice_date": invoice_date.group(1).rstrip(".") if invoice_date else "",
        "payment_due": payment_due.group(1).rstrip(".") if payment_due else "",
        "performance_date": (
            performance_date.group(1).rstrip(".") if performance_date else ""
        ),
    }

    period_pattern = r"Időszak:\s*([\d\.]+ - [\d\.]+)"
    license_plate_pattern = r"Felszerelési hely:\s+(\S+)"
    line_pattern = r"Menetlevél \+ útdíj alapszolgáltatás[^\n]+"

    lines = re.findall(line_pattern, full_text)
    periods = re.findall(period_pattern, full_text)
    license_plates = re.findall(license_plate_pattern, full_text)

    min_len = min(len(periods), len(license_plates), len(lines))
    if min_len < max(len(periods), len(license_plates), len(lines)):
        print(
            "Warning: not all data is present for each row! Only matching triples will be paired."
        )

    data = []
    for i in range(min_len):
        line = lines[i]

        amounts = re.findall(r"(\d{1,3}(?: \d{3})*,\d{2})Ft", line)
        vat_percent = re.search(r"(\d{1,2})\s?%", line)

        if len(amounts) >= 4 and vat_percent:
            net = float(amounts[1].replace(" ", "").replace(",", "."))
            vat = int(vat_percent.group(1))
            vat_amount = float(amounts[2].replace(" ", "").replace(",", "."))
            period_start, period_end = [p.strip() for p in periods[i].split(" - ")]
            license_plate = license_plates[i].replace(" ", "").replace("-", "")
            row = {
                **header_info,
                "period_start": period_start,
                "period_end": period_end,
                "license_plate": license_plate,
                "net": net,
                "vat_percent": vat,
                "vat_amount": vat_amount,
            }
            data.append(row)

    return data


def process_volvo(pdf_bytes: bytes):

    data = []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:

        first_page_text = pdf.pages[0].extract_text()
        tables = pdf.pages[0].extract_tables()

        invoice_number = ""
        if tables and len(tables[0]) >= 2:
            row = tables[0][1]
            invoice_number = row[0]

        invoice_date = payment_due = performance_date = ""
        lines = first_page_text.splitlines()
        for line in lines:
            dates = re.findall(r"\d{2}-\d{2}-\d{4}", line)
            if len(dates) >= 3:
                invoice_date, payment_due, performance_date = dates[:3]
                break

        header_info = {
            "invoice_number": invoice_number,
            "invoice_date": invoice_date,
            "payment_due": payment_due,
            "performance_date": performance_date,
        }

        for page in pdf.pages:
            tables = page.extract_tables()
            if len(tables) >= 2:
                table = tables[1]

                for row in table:
                    flat_row = " ".join(row).replace("\n", " ")
                    row_with_breaks = " ".join(row).split("\n")

                    license_plate = ""
                    if len(row_with_breaks) > 1:
                        after_newline = row_with_breaks[1]
                        match = re.search(r"(.+?)\s*\d{2}-\d{2}-\d{4}", after_newline)
                        if match:
                            raw_license = match.group(1)
                            license_plate = raw_license.replace(" ", "").replace(
                                "-", ""
                            )
                        # else:
                        #     license_plate = after_newline.split()[0].replace(" ", "").replace("-", "")

                    dates = re.findall(r"\d{2}-\d{2}-\d{4}", flat_row)
                    period_start = dates[0] if len(dates) > 0 else ""
                    period_end = dates[1] if len(dates) > 1 else ""

                    amounts = re.findall(r"\d{1,3}(?:\.\d{3})*,\d{2}", flat_row)
                    amount = amounts[-1] if amounts else ""

                    if period_start and license_plate and period_end and amount:
                        data.append(
                            {
                                **header_info,
                                "period_start": period_start,
                                "period_end": period_end,
                                "license_plate": license_plate,
                                "net": amount,
                            }
                        )

    return data


def process_vodafone(pdf_bytes: bytes):

    invoice_summary_rows = []
    service_charge_rows = []
    invoice_number = ""

    def process_invoice_page(text: str):
        start = text.find("Számlaösszesítő")
        end = text.find("Egyenlegközlő információ")
        if start == -1 or end == -1:
            return
        for line in text[start:end].split("\n"):
            if any(
                k in line
                for k in ["összeg", "Megnevezés", "Összesen", "Számlaösszesítő"]
            ):
                continue

            teszor_match = re.search(r"\b\d{2}\.\d{2}\.\d{1,2}\b", line)
            if teszor_match:
                parts = line.rsplit(" ", 8)
                if len(parts) == 9:
                    invoice_summary_rows.append(parts)
            else:
                parts = line.rsplit(" ", 7)
                if len(parts) == 8:
                    parts.insert(4, "")  # empty TESZOR field
                    invoice_summary_rows.append(parts)

    def process_service_charges(lines):
        phone_number = "N/A"
        for line in lines:
            if "Tarifacsomag:" in line:
                break
            match = re.search(r"Telefonszám:\s*(36\d{9})", line)
            if match:
                phone_number = match.group(1)
                break

        try:
            start_index = next(
                i
                for i, line in enumerate(lines)
                if line.strip().startswith("Megnevezés")
            )
            end_index = next(
                i
                for i, line in enumerate(lines)
                if line.strip().startswith("Kiszámlázott díjak összesen")
            )
        except StopIteration:
            return

        for line in lines[start_index + 1 : end_index]:
            teszor_match = re.search(r"\b\d{2}\.\d{2}\.\d{1,2}\b", line)
            if not teszor_match:
                continue

            teszor = teszor_match.group()
            parts = line.rsplit(" ", 4)
            if len(parts) < 5:
                continue

            total_amount, vat_amount, vat_rate, net_amount = parts[-4:]
            before_values = parts[0]
            description = (
                before_values.split(teszor)[0].strip()
                if teszor in before_values
                else before_values.strip()
            )

            service_charge_rows.append(
                [
                    phone_number,
                    description,
                    teszor,
                    net_amount,
                    vat_rate,
                    vat_amount,
                    total_amount,
                ]
            )

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:

        is_service_section = False
        service_lines_accumulator = []

        for i, page in enumerate(pdf.pages):
            text = page.extract_text() or ""
            if not text:
                continue
            lines = text.split("\n")
            header = lines[0].strip().upper()

            if i == 1 and invoice_number is "":
                for line in lines:
                    m = re.search(r"Számlaszám[:\s]+(\d+)", line)
                    if m:
                        invoice_number = m.group(1)
                        break

            if header in ["KISZÁMLÁZOTT DÍJAK", "ÜGYFÉLSZINTŰ DÍJAK"]:
                is_service_section = True
                service_lines_accumulator.extend(lines)

            elif is_service_section:
                service_lines_accumulator.extend(lines)

            if is_service_section and any(
                "Kiszámlázott díjak összesen" in line for line in lines
            ):
                process_service_charges(service_lines_accumulator)
                is_service_section = False
                service_lines_accumulator = []

            if header == "SZÁMLA":
                process_invoice_page(text)

    return {
        "invoice_number": invoice_number,
        "invoice_summary": invoice_summary_rows,
        "service_charges": service_charge_rows,
    }
