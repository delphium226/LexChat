from fastapi import APIRouter, HTTPException
from database import db
from services.auth import get_password_hash
from faker import Faker
import logging
import random
from datetime import datetime, timedelta
from config import settings

logger = logging.getLogger("lexchat.developer")
router = APIRouter(prefix="/api/developer", tags=["Developer"])
faker = Faker()

@router.post("/seed")
async def seed_data():
    try:
        logger.info("Starting synthetic data generation...")
        hashed_password = get_password_hash('password123')
        users_to_create = 100
        user_ids = []

        # 1. Create Users
        # Optimization: Prepare all data then insert? Asyncpg 'executemany' is fast.
        # But for logic simplicity (check existing), we'll loop.
        
        for _ in range(users_to_create):
            first_name = faker.first_name()
            last_name = faker.last_name()
            # unique username
            username = f"{faker.user_name()}{random.randint(100,999)}".lower()
            email = faker.email()
            
            # Check existing
            existing = await db.fetch_one("SELECT id FROM users WHERE username = $1", username)
            if not existing:
                row = await db.fetch_one(
                    "INSERT INTO users (username, password_hash, role, email) VALUES ($1, $2, $3, $4) RETURNING id",
                    username, hashed_password, 'user', email
                )
                user_ids.append(row['id'])
            else:
                user_ids.append(existing['id'])

        logger.info(f"Created/Found {len(user_ids)} users.")

        # 2. Generate History (6 months)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=180) # ~6 months
        
        total_chats = 0
        total_messages = 0
        
        current_date = start_date
        while current_date <= end_date:
            # Simulate activity per week
             for user_id in user_ids:
                 if random.random() < 0.3: # 30% chance per user per week
                     chats_this_week = random.randint(1, 3)
                     
                     for _ in range(chats_this_week):
                         # Random time within this week (0-6 days, random hours)
                         chat_date = current_date + timedelta(
                             days=random.randint(0, 6),
                             hours=random.randint(0, 23),
                             minutes=random.randint(0, 59)
                         )
                         
                         if chat_date > end_date:
                             continue
                             
                         legal_topics = ['Contract Law', 'Tort Liability', 'GDPR Compliance', 'Employment Rights', 'Property Dispute', 'Intellectual Property']
                         topic = random.choice(legal_topics)
                         title = f"{topic} Inquiry"
                         
                         # Get models from config? Or hardcode list matching Node.js
                         # Node.js: deepseek-v3.2:cloud, mistral-large-3:675b-cloud, kimi-k2-thinking:cloud
                         models = ["deepseek-v3.2:cloud", "mistral-large-3:675b-cloud", "kimi-k2-thinking:cloud"]
                         random_model = random.choice(models)
                         
                         # Create Chat
                         chat_row = await db.fetch_one(
                             "INSERT INTO chats (user_id, title, model, created_at) VALUES ($1, $2, $3, $4) RETURNING id",
                             user_id, title, random_model, chat_date
                         )
                         chat_id = chat_row['id']
                         total_chats += 1
                         
                         # Create Messages
                         # User
                         await db.execute(
                             "INSERT INTO messages (chat_id, role, content, created_at) VALUES ($1, $2, $3, $4)",
                             chat_id, 'user', f"I have a question about {topic}.", chat_date
                         )
                         
                         # Assistant
                         response_date = chat_date + timedelta(seconds=5)
                         
                         rating = None
                         comment = None
                         
                         if random.random() < 0.5: # 50% chance of rating
                             r_rand = random.random()
                             if r_rand < 0.1: rating = 1
                             elif r_rand < 0.2: rating = 2
                             elif r_rand < 0.4: rating = 3
                             elif r_rand < 0.7: rating = 4
                             else: rating = 5
                             
                             if random.random() < 0.4:
                                 comment = faker.sentence()
                        
                         await db.execute(
                             "INSERT INTO messages (chat_id, role, content, created_at, rating, feedback_comment) VALUES ($1, $2, $3, $4, $5, $6)",
                             chat_id, 'assistant', f"Here is some information regarding {topic}... [Synthetic Response]", response_date, rating, comment
                         )
                         total_messages += 2

            # Advance one week
             current_date += timedelta(days=7)

        return {
            "success": True,
            "message": "Synthetic data generated successfully.",
            "stats": {
                "users": len(user_ids),
                "chats": total_chats,
                "messages": total_messages
            }
        }

    except Exception as e:
        logger.error(f"Seed error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reset")
async def reset_database():
    try:
        logger.info("Resetting database...")
        # Delete message, chats, users > cascade usually handles message/chats if users deleted?
        # Node implementation deleted explicitly.
        
        await db.execute("DELETE FROM messages")
        await db.execute("DELETE FROM chats")
        await db.execute("DELETE FROM users WHERE username != 'admin'")
        
        return {"success": True, "message": "Database reset successfully. Only admin user remains."}
    except Exception as e:
        logger.error(f"Reset error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
