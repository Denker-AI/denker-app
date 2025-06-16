from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any
from inspect import isawaitable
from db.database import get_db
from db.repositories import MemoryRepository
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

@router.post("/entities")
async def create_entities(data: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    return await MemoryRepository(db).create_entities(data["entities"])

@router.post("/relations")
async def create_relations(data: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    return await MemoryRepository(db).create_relations(data["relations"])

@router.post("/observations")
async def add_observations(data: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    return await MemoryRepository(db).add_observations(data["observations"])

@router.post("/entities/delete")
async def delete_entities(data: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    return await MemoryRepository(db).delete_entities(data["entityNames"])

@router.post("/relations/delete")
async def delete_relations(data: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    return await MemoryRepository(db).delete_relations(data["relations"])

@router.post("/entities/update")
async def update_entities(data: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    return await MemoryRepository(db).update_entities(data["entities"])

@router.post("/relations/update")
async def update_relations(data: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    return await MemoryRepository(db).update_relations(data["relations"])

@router.get("/graph")
async def read_graph(db: AsyncSession = Depends(get_db)):
    return await MemoryRepository(db).read_graph()

@router.get("/search")
async def search_nodes(query: str, db: AsyncSession = Depends(get_db)):
    return await MemoryRepository(db).search_nodes(query)

@router.post("/nodes")
async def open_nodes(data: Dict[str, Any], db: AsyncSession = Depends(get_db)):
    return await MemoryRepository(db).open_nodes(data["names"])

@router.get("/health")
async def memory_health():
    return {"status": "ok", "message": "Memory backend is reachable"} 