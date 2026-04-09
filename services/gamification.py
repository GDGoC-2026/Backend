from datetime import date, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from Backend.models.gamification import UserStats, DailyStreak

class GamificationEngine:
    XP_PER_LEVEL = 100

    @staticmethod
    async def award_xp(db: AsyncSession, user_id: str, amount: int) -> dict:
        result = await db.execute(select(UserStats).where(UserStats.user_id == user_id))
        stats = result.scalar_one_or_none()

        if not stats:
            stats = UserStats(user_id=user_id, total_xp=0, current_level=1, longest_streak=0)
            db.add(stats)

        stats.total_xp += amount
        # Calculate level ups
        new_level = (stats.total_xp // GamificationEngine.XP_PER_LEVEL) + 1
        level_up = new_level > stats.current_level
        stats.current_level = new_level

        await db.commit()
        return {"xp_awarded": amount, "total_xp": stats.total_xp, "level_up": level_up, "current_level": stats.current_level}

    @staticmethod
    async def update_streak(db: AsyncSession, user_id: str) -> dict:
        today = date.today()
        result = await db.execute(select(DailyStreak).where(DailyStreak.user_id == user_id))
        streak = result.scalar_one_or_none()

        streak_maintained = False

        if not streak:
            streak = DailyStreak(user_id=user_id, last_activity_date=today)
            db.add(streak)
            current_streak = 1
        else:
            delta = today - streak.last_activity_date
            if delta == timedelta(days=1):
                # Consecutive day
                current_streak += 1
                streak.last_activity_date = today
                streak_maintained = True
            elif delta > timedelta(days=1):
                # Streak broken
                current_streak = 1
                streak.last_activity_date = today
            else:
                # Already active today
                streak_maintained = True

        # Update longest streak stat
        stats_result = await db.execute(select(UserStats).where(UserStats.user_id == user_id))
        stats = stats_result.scalar_one_or_none()
        if stats and current_streak > stats.longest_streak:
            stats.longest_streak = current_streak

        await db.commit()
        return {"current_streak": current_streak, "maintained": streak_maintained}