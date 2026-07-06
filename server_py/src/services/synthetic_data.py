"""Synthetic test-data generation for the Admin Portal Developer tab.

Moved out of routers/developer.py so the router holds only endpoints.
"""

import logging
import random
from datetime import datetime, timedelta

from faker import Faker
from passlib.hash import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import MODEL_LIST
from ..models import Chat, Message, User

logger = logging.getLogger("app")

fake = Faker()


async def generate_synthetic_data(db: AsyncSession) -> dict:
    """Generate 100 synthetic users with 6 months of chat history."""
    hashed_password = bcrypt.using(rounds=10).hash("password123")
    users_to_create = 100
    user_ids = []

    # 1. Create users
    for _ in range(users_to_create):
        first = fake.first_name()
        last = fake.last_name()
        username = (
            fake.user_name()[:15].lower().replace(".", "")
            + str(random.randint(100, 999))
        )
        email = fake.email()

        # Check if exists
        existing = await db.execute(
            select(User.id).where(User.username == username)
        )
        row = existing.scalar_one_or_none()
        if row:
            user_ids.append(row)
        else:
            new_user = User(
                username=username,
                password_hash=hashed_password,
                role="user",
                email=email,
            )
            db.add(new_user)
            await db.flush()
            user_ids.append(new_user.id)

    await db.commit()

    # 2. Generate 6 months of history
    end_date = datetime.utcnow()
    start_date = end_date - timedelta(days=180)

    legal_topics = [
        "Contract Law", "Tort Liability", "GDPR Compliance",
        "Employment Rights", "Property Dispute", "Intellectual Property",
    ]
    model_names = [m["name"] for m in MODEL_LIST]

    total_chats = 0
    total_messages = 0

    current_date = start_date
    while current_date <= end_date:
        for user_id in user_ids:
            # 30% chance of activity per user per week
            if random.random() < 0.3:
                chats_this_week = random.randint(1, 3)

                for _ in range(chats_this_week):
                    chat_date = current_date + timedelta(
                        days=random.randint(0, 6),
                        hours=random.randint(0, 23),
                        minutes=random.randint(0, 59),
                    )
                    if chat_date > end_date:
                        continue

                    topic = random.choice(legal_topics)
                    model = random.choice(model_names)

                    chat = Chat(
                        user_id=user_id,
                        title=f"{topic} Inquiry",
                        model=model,
                        created_at=chat_date,
                    )
                    db.add(chat)
                    await db.flush()
                    total_chats += 1

                    # User message
                    user_msg = Message(
                        chat_id=chat.id,
                        role="user",
                        content=f"I have a question about {topic}.",
                        created_at=chat_date,
                    )
                    db.add(user_msg)

                    # Assistant message
                    response_date = chat_date + timedelta(seconds=5)
                    rating = None
                    comment = None

                    if random.random() < 0.5:
                        rand = random.random()
                        if rand < 0.1:
                            rating = 1
                        elif rand < 0.2:
                            rating = 2
                        elif rand < 0.4:
                            rating = 3
                        elif rand < 0.7:
                            rating = 4
                        else:
                            rating = 5

                        if random.random() < 0.4:
                            comment = fake.sentence()

                    assistant_msg = Message(
                        chat_id=chat.id,
                        role="assistant",
                        content=f"Here is some information regarding {topic}... [Synthetic Response]",
                        created_at=response_date,
                        rating=rating,
                        feedback_comment=comment,
                    )
                    db.add(assistant_msg)
                    total_messages += 2

        # Advance one week
        current_date += timedelta(days=7)

    await db.commit()

    logger.info(f"[Developer] Seed complete: {len(user_ids)} users, {total_chats} chats, {total_messages} messages")
    return {
        "success": True,
        "message": "Synthetic data generated successfully.",
        "stats": {
            "users": len(user_ids),
            "chats": total_chats,
            "messages": total_messages,
        },
    }
