from sqlalchemy.orm import Session

from app.models.processed_event import ProcessedEvent


def event_already_processed(
    db: Session,
    event_id: str
) -> bool:

    event = (
        db.query(ProcessedEvent)
        .filter(
            ProcessedEvent.event_id == event_id
        )
        .first()
    )

    return event is not None


def mark_event_processed(
    db: Session,
    event_id: str
):

    processed_event = ProcessedEvent(
        event_id=event_id
    )

    db.add(processed_event)
