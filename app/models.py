"""Pydantic models for Epic order history and weekly promotions."""

from typing import List

from pydantic import BaseModel, Field


class OrderItem(BaseModel):
    description: str
    offerId: str
    namespace: str


class Order(BaseModel):
    orderType: str
    orderId: str
    items: List[OrderItem] = Field(default_factory=list)


class PromotionGame(BaseModel):
    title: str
    id: str
    namespace: str
    description: str
    offerType: str
    url: str
