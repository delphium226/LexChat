import asyncio
import os
import sys

# Add server_py to path (repo root is two levels up from scripts/dev/)
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "server_py")))

from src.database import async_session_maker
from src.models import Chat, User, Message
from sqlalchemy import select

async def main():
    async with async_session_maker() as session:
        # Check users
        result = await session.execute(select(User))
        users = result.scalars().all()
        print(f"Users: {len(users)}")
        for u in users:
            print(f"  - {u.username} (id: {u.id})")

        # Check chats
        result = await session.execute(select(Chat))
        chats = result.scalars().all()
        print(f"Chats: {len(chats)}")
        for c in chats:
            print(f"  - Chat ID: {c.id}, User ID: {c.user_id}, Title: {c.title}")

        # Check messages
        result = await session.execute(select(Message))
        messages = result.scalars().all()
        print(f"Messages: {len(messages)}")

if __name__ == "__main__":
    asyncio.run(main())
