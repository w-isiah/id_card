# apps/fastapi_app.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
from apps.db import get_db_connection  # Database helper for FastAPI

# FastAPI instance
fastapi_app = FastAPI()

class Category(BaseModel):
    CategoryID: int
    name: str

@fastapi_app.get("/categories", response_model=List[Category])
async def get_categories():
    """Fetch categories from the database."""
    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM category_list")
        categories = cursor.fetchall()

        if not categories:
            raise HTTPException(status_code=404, detail="Categories not found")

        return categories
    finally:
        cursor.close()
        connection.close()
