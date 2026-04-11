from datetime import date, timedelta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from Backend.models.gamification import UserStats, DailyStreak


class GamificationEngine:
    XP_PER_LEVEL = 100


    @staticmethod
    def calculate_rank(level: int) -> str:
        """Returns a string rank based on the user's level."""
        ranks = [
            (1, "Novice Scholar"),
            (5, "Apprentice Learner"),
            (10, "Adept Student"),
            (20, "Knowledge Seeker"),
            (35, "Master Thinker"),
            (50, "Grandmaster Polymath"),
            (100, "Apex Scholar")
        ]
        current_rank = ranks[0][1]
        for threshold, rank_name in ranks:
            if level >= threshold:
                current_rank = rank_name
            else:
                break
        return current_rank


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
        return {
            "xp_awarded": amount, 
            "total_xp": stats.total_xp, 
            "level_up": level_up, 
            "current_level": stats.current_level,
            "rank": GamificationEngine.calculate_rank(stats.current_level)
        }


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


    @staticmethod
    async def get_leaderboard(db: AsyncSession, limit: int = 10) -> list[dict]:
        """Fetch the top users by total XP."""
        from Backend.models.user import User
        # Join UserStats with User to get full names, sort by XP descending
        stmt = (
            select(UserStats, User.full_name)
            .join(User, UserStats.user_id == User.id)
            .order_by(UserStats.total_xp.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        rows = result.all()
        
        leaderboard = []
        for rank, (stats, name) in enumerate(rows, start=1):
            leaderboard.append({
                "rank_position": rank,
                "user_id": str(stats.user_id),
                "name": name or "Anonymous Learner",
                "level": stats.current_level,
                "rank_title": GamificationEngine.calculate_rank(stats.current_level),
                "total_xp": stats.total_xp,
                "longest_streak": stats.longest_streak
            })
        return leaderboard