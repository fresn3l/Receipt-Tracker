import json

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from receipts.database import get_db
from receipts.export_service import export_csv, export_json
from receipts.import_service import import_json_data
from receipts.schemas import ImportRequest, ImportResult

router = APIRouter(tags=["data"])


@router.get("/export/json")
def export_data_json(db: Session = Depends(get_db)):
    return export_json(db)


@router.get("/export/csv")
def export_data_csv(db: Session = Depends(get_db)):
    return Response(
        content=export_csv(db),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=receipts.csv"},
    )


@router.post("/import/json", response_model=ImportResult)
def import_data_json(payload: ImportRequest, db: Session = Depends(get_db)):
    try:
        result = import_json_data(db, payload.data, replace=payload.replace)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Import failed: {exc}") from exc
    return ImportResult(**result)


@router.post("/import/json/file", response_model=ImportResult)
async def import_data_json_file(
    file: UploadFile = File(...),
    replace: bool = Query(False),
    db: Session = Depends(get_db),
):
    try:
        payload = json.loads(await file.read())
        result = import_json_data(db, payload, replace=replace)
        db.commit()
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON file.") from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Import failed: {exc}") from exc
    return ImportResult(**result)
