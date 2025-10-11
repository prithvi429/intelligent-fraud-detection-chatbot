from fastapi import APIRouter

router = APIRouter(prefix="/guidance", tags=["guidance"])

@router.post("/")
def get_guidance():
    return {"required_docs": ["ID", "Invoice"]}
