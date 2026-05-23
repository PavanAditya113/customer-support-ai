from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
import datetime

class TicketRaw(Base):
    __tablename__ = "tickets_raw"

    ticket_id                   = Column(String, primary_key=True)
    customer_id                 = Column(String)
    ticket_created_date         = Column(DateTime)
    ticket_resolved_date        = Column(DateTime)
    channel                     = Column(String)
    issue_description           = Column(Text)
    resolution_notes            = Column(Text)
    category                    = Column(String)
    priority                    = Column(String)
    status                      = Column(String)
    product                     = Column(String)
    region                      = Column(String)
    subscription_type           = Column(String)
    customer_segment            = Column(String)
    customer_tenure_months      = Column(Integer)
    previous_tickets            = Column(Integer)
    customer_satisfaction_score = Column(Integer)
    first_response_time_hours   = Column(Float)
    resolution_time_hours       = Column(Float)
    sla_breached                = Column(Boolean)
    escalated                   = Column(Boolean)
    language                    = Column(String)
    issue_complexity_score      = Column(Integer)
    order_value                 = Column(Float)

    enriched = relationship("TicketEnriched", back_populates="ticket", uselist=False)


class TicketEnriched(Base):
    __tablename__ = "tickets_enriched"

    ticket_id          = Column(String, ForeignKey("tickets_raw.ticket_id"), primary_key=True)
    sentiment          = Column(String)
    frustration_level  = Column(Integer)
    issue_summary      = Column(Text)
    suggested_response = Column(Text)
    processed_at       = Column(DateTime, default=datetime.datetime.utcnow)

    ticket = relationship("TicketRaw", back_populates="enriched")
