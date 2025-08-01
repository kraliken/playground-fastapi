import re
import pandas as pd
from io import BytesIO


def export_volvo_to_excel_bytes(data):
    if not data:
        return None
    df = pd.DataFrame(data)
    for col in [
        "period_start",
        "period_end",
        "invoice_date",
        "payment_due",
        "performance_date",
    ]:
        try:
            df[col] = pd.to_datetime(df[col], format="%d-%m-%Y")
        except Exception:
            df[col] = df[col]

    df["net"] = (
        df["net"]
        .str.replace(".", "", regex=False)
        .str.replace(",", ".", regex=False)
        .astype(float)
    )
    df["vat"] = (df["net"] * 0.27).round(0)
    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    return output


def export_multialarm_to_excel_bytes(data):
    if not data:
        return None

    df = pd.DataFrame(data)
    for col in [
        "period_start",
        "period_end",
        "invoice_date",
        "payment_due",
        "performance_date",
    ]:
        try:
            df[col] = pd.to_datetime(df[col], format="%Y.%m.%d")
        except Exception:
            df[col] = df[col]

    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)

    return output


def export_vodafone_to_excel_bytes(
    result, phone_user_map, teszor_category_map, mapping_lookup
):
    def extract_mapping_info(row):
        key = (row["TESZOR"], row["VATRate"])
        return pd.Series(
            mapping_lookup.get(
                key,
                {
                    "Title": "Ismeretlen",
                    "VatCode": "Ismeretlen",
                    "LedgerAccount": "Ismeretlen",
                },
            )
        )

    def _clean_float(value):
        try:
            cleaned = value.replace(".", "").replace(",", ".").strip()
            return float(cleaned) if re.match(r"^-?\d+(\.\d+)?$", cleaned) else None
        except Exception:
            return None

    excel_buffer = BytesIO()

    with pd.ExcelWriter(excel_buffer, engine="openpyxl") as writer:
        if result["invoice_summary"]:
            df_summary = pd.DataFrame(
                result["invoice_summary"],
                columns=[
                    "Megnevezés",
                    "Mennyiség",
                    "Mennyiségi egység",
                    "Egységár (Ft)",
                    "TESZOR szám",
                    "ÁFA kulcs",
                    "Nettó összeg (Ft)",
                    "ÁFA összeg (Ft)",
                    "Bruttó összeg (Ft)",
                ],
            )

            for col in [
                "Egységár (Ft)",
                "Nettó összeg (Ft)",
                "ÁFA összeg (Ft)",
                "Bruttó összeg (Ft)",
            ]:
                df_summary[col] = (
                    df_summary[col]
                    .astype(str)
                    .str.replace(".", "", regex=False)
                    .str.replace(",", ".", regex=False)
                    .astype(float)
                )

            df_summary.to_excel(writer, sheet_name="InvoiceSummary", index=False)

        if result["service_charges"]:
            df_charges = pd.DataFrame(
                result["service_charges"],
                columns=[
                    "PhoneNumber",
                    "Description",
                    "TESZOR",
                    "TotalAmount",
                    "VATAmount",
                    "VATRate",
                    "NetAmount",
                ],
            )
            df_charges["Employee"] = df_charges["PhoneNumber"].map(
                lambda pn: phone_user_map.get(pn, {}).get("name", "N/A")
            )
            df_charges["Cost Center"] = df_charges["PhoneNumber"].map(
                lambda pn: phone_user_map.get(pn, {}).get("cost_center", "N/A")
            )
            df_charges["Monogram"] = df_charges["PhoneNumber"].map(
                lambda pn: phone_user_map.get(pn, {}).get("monogram", "N/A")
            )
            df_charges["Axapta Name"] = df_charges["PhoneNumber"].map(
                lambda pn: phone_user_map.get(pn, {}).get("axapta_name", "N/A")
            )

            df_charges["LedgerTitle"] = (
                df_charges["TESZOR"].map(teszor_category_map).fillna("N/A")
            )

            title_df = df_charges.apply(extract_mapping_info, axis=1)
            df = pd.concat([df_charges, title_df], axis=1)

            for col in ["NetAmount", "VATAmount", "TotalAmount"]:
                df[col] = df_charges[col].apply(_clean_float)

            df.to_excel(writer, sheet_name="ServiceCharges", index=False)

            # df.loc[df["Employee"] == "Központi", "PhoneNumber"] = "N/A"
            mask = (df["Employee"] == "Központi") & (
                df["PhoneNumber"].isna()
                | (df["PhoneNumber"] == "")
                | (df["PhoneNumber"] == "N/A")
            )
            df.loc[mask, "PhoneNumber"] = "Központi"
            df.loc[df["Employee"] == "Központi", "Axapta Name"] = "N/A"

            if not df.empty:
                pivot_df = pd.pivot_table(
                    df,
                    index=[
                        "PhoneNumber",
                        "Employee",
                        "Cost Center",
                        "Axapta Name",
                        "Monogram",
                        "VATRate",
                        "Title",
                        "VatCode",
                        "LedgerAccount",
                    ],
                    values=["NetAmount", "VATAmount"],
                    aggfunc="sum",
                    fill_value=0,
                ).reset_index()
                pivot_df.to_excel(writer, sheet_name="Pivot", index=False)

    excel_buffer.seek(0)
    return excel_buffer
