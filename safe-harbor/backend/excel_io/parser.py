import openpyxl
import re

class InvalidTemplateError(Exception): pass
class TemplateNotEmptyError(Exception): pass

def parse_template(file_path: str) -> dict:
    try:
        wb = openpyxl.load_workbook(file_path, data_only=False)
    except Exception as e:
        raise InvalidTemplateError(f"Corrupt or unsupported Excel file: {e}")

    result = {
        "file_name": file_path.split("/")[-1],
        "sheets": [],
        "named_ranges": [],
        "inter_sheet_refs": [],
        "total_input_cells": 0
    }

    year_pattern = re.compile(r"(FY|CY)?\d{4}[EA]?")
    inter_sheet_pattern = re.compile(r"'?([^'!]+)'?!([A-Z]+\d+)")

    total_input = 0
    total_cells_checked = 0
    populated_input = 0

    for ws in wb.worksheets:
        sheet_data = {
            "name": ws.title,
            "headers": [],
            "input_cells": [],
            "formula_cells": [],
            "temporal_headers": []
        }

        period_headers = []
        for col in range(2, ws.max_column + 1):
            val = ws.cell(row=1, column=col).value or ws.cell(row=2, column=col).value
            if val and year_pattern.search(str(val)):
                period_headers.append({"col": col, "val": str(val).strip()})
                if str(val).strip() not in sheet_data["temporal_headers"]:
                    sheet_data["temporal_headers"].append(str(val).strip())

        for row in range(2, ws.max_row + 1):
            line_item_val = ws.cell(row=row, column=1).value
            if not line_item_val:
                continue
            
            header_name = str(line_item_val).strip()
            sheet_data["headers"].append({"row": row, "header": header_name})

            for p in period_headers:
                cell = ws.cell(row=row, column=p["col"])
                val = cell.value
                coord = cell.coordinate
                
                total_cells_checked += 1
                if val is None or str(val).strip() == "":
                    sheet_data["input_cells"].append({"ref": coord, "column_header": header_name, "period": p["val"]})
                    total_input += 1
                elif isinstance(val, str) and val.startswith("="):
                    sheet_data["formula_cells"].append({"ref": coord, "formula": val, "column_header": header_name})
                    
                    matches = inter_sheet_pattern.findall(val)
                    for match in matches:
                        target_sheet, target_cell = match
                        if target_sheet != ws.title:
                            result["inter_sheet_refs"].append({
                                "source_sheet": ws.title,
                                "source_cell": coord,
                                "target_sheet": target_sheet,
                                "target_cell": target_cell
                            })
                else:
                    populated_input += 1
                    sheet_data["input_cells"].append({"ref": coord, "column_header": header_name, "period": p["val"]})
                    total_input += 1

        result["sheets"].append(sheet_data)

    if total_input > 0 and (populated_input / total_input) > 0.05:
        raise TemplateNotEmptyError("File contains too much data in input cells. Upload an empty template.")

    result["total_input_cells"] = total_input

    for name in wb.defined_names.definedName:
        result["named_ranges"].append({
            "name": name.name,
            "cell_range": name.attr_text
        })

    return result
