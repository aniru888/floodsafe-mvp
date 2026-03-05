from sqlalchemy.orm import Session
from typing import Dict, List, Optional
from uuid import UUID
from datetime import datetime, timedelta
import json
import logging

from ...infrastructure import models

logger = logging.getLogger(__name__)

# ============================================================================
# POINTS SYSTEM CONFIGURATION
# ============================================================================

POINTS_SYSTEM = {
    'report_submitted': 5,
    'report_verified_base': 10,
    'report_rejected': -5,
    'report_upvoted': 1,
    'streak_7': 25,
    'streak_30': 100,
}


# ============================================================================
# CORE CALCULATION FUNCTIONS
# ============================================================================

def calculate_quality_score(report: models.Report) -> float:
    """
    Calculate quality score (0-100) based on multiple factors
    Simple and effective scoring system
    """
    score = 50.0  # Base score for any report

    # 1. Media presence (+25 points)
    if report.media_url:
        score += 20
        if report.media_type == 'video':
            score += 5

    # 2. Description quality (+15 points)
    if report.description and len(report.description) > 20:
        score += 15

    # 3. Community validation (+10 points)
    if report.upvotes > 0:
        score += min(report.upvotes * 2, 10)

    # 4. Penalty for downvotes
    if report.downvotes > 2:
        score -= min(report.downvotes * 3, 15)

    return max(0, min(score, 100))  # Clamp 0-100


def calculate_quality_bonus(quality_score: float) -> int:
    """
    Calculate bonus points based on quality score
    Returns 0-10 bonus points
    """
    return int(quality_score / 10)


def calculate_level(points: int) -> int:
    """
    Calculate level based on points
    Linear progression: 1 level per 100 points
    """
    return (points // 100) + 1


def points_to_next_level(current_points: int) -> int:
    """Calculate points needed for next level"""
    return 100 - (current_points % 100)


def calculate_reputation_score(user: models.User) -> int:
    """
    Calculate reputation score (0-100) based on:
    - Accuracy (main factor)
    - Consistency (streak)
    - Volume (total verified)
    """
    if user.reports_count == 0:
        return 0

    # Core: Verification rate (0-100)
    accuracy = (user.verified_reports_count / user.reports_count) * 100

    # Small bonus for consistency (max +20)
    consistency_bonus = min(user.streak_days * 2, 20)

    # Small bonus for volume (max +10)
    volume_bonus = min(user.verified_reports_count / 5, 10)

    reputation = int(accuracy + consistency_bonus + volume_bonus)

    return min(reputation, 100)  # Cap at 100


def calculate_accuracy_rate(user: models.User) -> float:
    """Calculate user's accuracy rate as percentage"""
    if user.reports_count == 0:
        return 0.0
    return (user.verified_reports_count / user.reports_count) * 100


# ============================================================================
# REPUTATION SERVICE CLASS
# ============================================================================

class ReputationService:
    """
    Core reputation system service
    Handles all reputation-related business logic
    """

    def __init__(self, db: Session):
        self.db = db

    def process_report_verification(
        self,
        report_id: UUID,
        verified: bool,
        quality_score: Optional[float] = None
    ) -> Dict:
        """
        Main entry point for report verification
        Handles all reputation updates
        """
        try:
            report = self.db.query(models.Report).filter(
                models.Report.id == report_id
            ).first()

            if not report:
                raise ValueError(f"Report {report_id} not found")

            # Skip reputation pipeline for admin-created reports
            if report.admin_created:
                return {
                    "points_earned": 0,
                    "quality_score": report.quality_score or 0,
                    "skipped": "admin_created",
                }

            user = self.db.query(models.User).filter(
                models.User.id == report.user_id
            ).first()

            if not user:
                raise ValueError(f"User {report.user_id} not found")

            if verified:
                return self._process_verified_report(report, user, quality_score)
            else:
                return self._process_rejected_report(report, user)

        except Exception as e:
            logger.error(f"Error processing report verification: {e}")
            self.db.rollback()
            raise

    def _process_verified_report(
        self,
        report: models.Report,
        user: models.User,
        quality_score: Optional[float] = None
    ) -> Dict:
        """Process a verified report and update user reputation"""

        # Calculate quality score if not provided
        if quality_score is None:
            quality_score = calculate_quality_score(report)

        report.quality_score = quality_score
        report.verified = True
        report.verified_at = datetime.utcnow()

        # Calculate points awarded
        base_points = POINTS_SYSTEM['report_verified_base']
        quality_bonus = calculate_quality_bonus(quality_score)
        total_points = base_points + quality_bonus

        # Update user stats
        user.points += total_points
        user.verified_reports_count += 1
        user.level = calculate_level(user.points)
        user.last_activity_date = datetime.utcnow()

        # Recalculate reputation
        user.reputation_score = calculate_reputation_score(user)

        # Log history
        self._log_history(
            user.id,
            'report_verified',
            total_points,
            user.points,
            f"Report verified (quality: {quality_score:.0f})",
            {
                'report_id': str(report.id),
                'quality_score': quality_score,
                'base_points': base_points,
                'quality_bonus': quality_bonus
            }
        )

        # Check for new badges
        self._check_and_award_badges(user)

        # Check for auto-promotion to verified_reporter
        promoted = self._check_auto_promotion(user)

        self.db.commit()

        result = {
            'user_id': user.id,
            'points': user.points,
            'level': user.level,
            'reputation_score': user.reputation_score,
            'quality_score': quality_score,
            'points_earned': total_points
        }

        if promoted:
            result['promoted_to'] = user.role

        return result

    def _process_rejected_report(
        self,
        report: models.Report,
        user: models.User
    ) -> Dict:
        """Process a rejected report and apply penalty"""

        penalty = POINTS_SYSTEM['report_rejected']
        user.points = max(0, user.points + penalty)  # Can't go negative
        user.reputation_score = calculate_reputation_score(user)

        # Log history
        self._log_history(
            user.id,
            'report_rejected',
            penalty,
            user.points,
            "Report was not verified"
        )

        self.db.commit()

        return {
            'user_id': user.id,
            'points': user.points,
            'level': user.level,
            'reputation_score': user.reputation_score,
            'penalty_applied': abs(penalty)
        }

    def update_streak(self, user_id: UUID) -> Optional[int]:
        """
        Update user streak - called when user submits report
        Returns bonus points if streak milestone reached
        """
        user = self.db.query(models.User).filter(
            models.User.id == user_id
        ).first()

        if not user:
            return None

        today = datetime.utcnow().date()

        if not user.last_activity_date:
            user.streak_days = 1
            user.last_activity_date = datetime.utcnow()
            self.db.commit()
            return None

        last_activity = user.last_activity_date.date()
        days_diff = (today - last_activity).days

        bonus_points = None

        if days_diff == 0:
            # Already active today
            return None
        elif days_diff == 1:
            # Streak continues
            user.streak_days += 1

            # Check for streak bonuses
            if user.streak_days == 7:
                bonus_points = POINTS_SYSTEM['streak_7']
            elif user.streak_days == 30:
                bonus_points = POINTS_SYSTEM['streak_30']

            if bonus_points:
                user.points += bonus_points
                user.level = calculate_level(user.points)
                self._log_history(
                    user_id,
                    f'streak_{user.streak_days}',
                    bonus_points,
                    user.points,
                    f"{user.streak_days} day streak bonus!"
                )

                # Check for badges
                self._check_and_award_badges(user)
        else:
            # Streak broken
            user.streak_days = 1

        user.last_activity_date = datetime.utcnow()
        self.db.commit()

        return bonus_points

    def process_report_upvote(self, report_id: UUID) -> Dict:
        """
        Process when a report receives an upvote
        Award small bonus to report owner
        """
        report = self.db.query(models.Report).filter(
            models.Report.id == report_id
        ).first()

        if not report:
            raise ValueError(f"Report {report_id} not found")

        user = self.db.query(models.User).filter(
            models.User.id == report.user_id
        ).first()

        if not user:
            return {}

        # Award small bonus
        bonus = POINTS_SYSTEM['report_upvoted']
        user.points += bonus
        user.level = calculate_level(user.points)

        self._log_history(
            user.id,
            'report_upvoted',
            bonus,
            user.points,
            "Your report received an upvote"
        )

        self.db.commit()

        return {
            'user_id': user.id,
            'points': user.points,
            'bonus': bonus
        }

    def get_reputation_summary(self, user_id: UUID) -> Dict:
        """Get complete reputation summary for a user"""
        user = self.db.query(models.User).filter(
            models.User.id == user_id
        ).first()

        if not user:
            raise ValueError(f"User {user_id} not found")

        # Count total available badges
        total_badges = self.db.query(models.Badge).filter(
            models.Badge.is_active == True
        ).count()

        # Count user's earned badges
        earned_badges = self.db.query(models.UserBadge).filter(
            models.UserBadge.user_id == user_id
        ).count()

        return {
            'user_id': user.id,
            'points': user.points,
            'level': user.level,
            'reputation_score': user.reputation_score,
            'accuracy_rate': calculate_accuracy_rate(user),
            'streak_days': user.streak_days,
            'next_level_points': points_to_next_level(user.points),
            'badges_earned': earned_badges,
            'total_badges': total_badges
        }

    def get_reputation_history(
        self,
        user_id: UUID,
        limit: int = 20,
        offset: int = 0
    ) -> List[models.ReputationHistory]:
        """Get user's reputation history"""
        return self.db.query(models.ReputationHistory).filter(
            models.ReputationHistory.user_id == user_id
        ).order_by(
            models.ReputationHistory.created_at.desc()
        ).limit(limit).offset(offset).all()

    def _check_and_award_badges(self, user: models.User):
        """
        Check if user qualifies for any new badges
        Award badges and bonus points automatically
        """
        # Get badges user doesn't have yet
        earned_badge_ids = self.db.query(models.UserBadge.badge_id).filter(
            models.UserBadge.user_id == user.id
        ).all()
        earned_ids = [b[0] for b in earned_badge_ids]

        available_badges = self.db.query(models.Badge).filter(
            models.Badge.is_active == True,
            models.Badge.id.notin_(earned_ids) if earned_ids else True
        ).all()

        for badge in available_badges:
            if self._check_badge_criteria(user, badge):
                # Award badge
                user_badge = models.UserBadge(
                    user_id=user.id,
                    badge_id=badge.id
                )
                self.db.add(user_badge)

                # Award points
                if badge.points_reward > 0:
                    user.points += badge.points_reward
                    user.level = calculate_level(user.points)

                    self._log_history(
                        user.id,
                        'badge_earned',
                        badge.points_reward,
                        user.points,
                        f"Earned badge: {badge.name}",
                        {'badge_key': badge.key}
                    )

                logger.info(f"User {user.id} earned badge: {badge.name}")

    def _check_badge_criteria(
        self,
        user: models.User,
        badge: models.Badge
    ) -> bool:
        """Check if user meets badge criteria"""
        requirement_type = badge.requirement_type
        requirement_value = badge.requirement_value

        # Map requirement types to user attributes
        user_value = 0

        if requirement_type == 'reports_count':
            user_value = user.reports_count
        elif requirement_type == 'verified_count':
            user_value = user.verified_reports_count
        elif requirement_type == 'points':
            user_value = user.points
        elif requirement_type == 'streak_days':
            user_value = user.streak_days
        elif requirement_type == 'level':
            user_value = user.level
        else:
            logger.warning(f"Unknown requirement type: {requirement_type}")
            return False

        return user_value >= requirement_value

    def _log_history(
        self,
        user_id: UUID,
        action: str,
        points_change: int,
        new_total: int,
        reason: str,
        metadata: Optional[Dict] = None
    ):
        """Log reputation history entry"""
        history = models.ReputationHistory(
            user_id=user_id,
            action=action,
            points_change=points_change,
            new_total=new_total,
            reason=reason,
            metadata=json.dumps(metadata) if metadata else "{}"
        )
        self.db.add(history)

    def get_badges_with_progress(self, user_id: UUID) -> Dict:
        """
        Get all badges with user's progress
        Returns earned badges and progress on locked badges
        """
        user = self.db.query(models.User).filter(
            models.User.id == user_id
        ).first()

        if not user:
            raise ValueError(f"User {user_id} not found")

        # Get all active badges
        all_badges = self.db.query(models.Badge).filter(
            models.Badge.is_active == True
        ).order_by(models.Badge.sort_order).all()

        # Get user's earned badges
        earned_badge_ids = self.db.query(models.UserBadge).filter(
            models.UserBadge.user_id == user_id
        ).all()
        earned_dict = {ub.badge_id: ub for ub in earned_badge_ids}

        earned = []
        in_progress = []

        for badge in all_badges:
            if badge.id in earned_dict:
                # Badge earned
                earned.append({
                    'badge': badge,
                    'earned_at': earned_dict[badge.id].earned_at
                })
            else:
                # Badge not earned - show progress
                current_value = self._get_user_value_for_requirement(
                    user,
                    badge.requirement_type
                )
                progress_percent = min(
                    (current_value / badge.requirement_value) * 100,
                    100
                )

                in_progress.append({
                    'badge': badge,
                    'current_value': current_value,
                    'required_value': badge.requirement_value,
                    'progress_percent': progress_percent
                })

        return {
            'earned': earned,
            'in_progress': in_progress
        }

    def _get_user_value_for_requirement(
        self,
        user: models.User,
        requirement_type: str
    ) -> int:
        """Get user's current value for a requirement type"""
        if requirement_type == 'reports_count':
            return user.reports_count
        elif requirement_type == 'verified_count':
            return user.verified_reports_count
        elif requirement_type == 'points':
            return user.points
        elif requirement_type == 'streak_days':
            return user.streak_days
        elif requirement_type == 'level':
            return user.level
        return 0

    def _check_auto_promotion(self, user: models.User) -> bool:
        """
        Check if user qualifies for auto-promotion to verified_reporter.

        Criteria:
        - Current role is "user"
        - At least 10 verified reports
        - Reputation score >= 70

        Returns True if promoted, False otherwise.
        """
        # Only promote users with "user" role
        if user.role != "user":
            return False

        # Check criteria: 10+ verified reports AND 70+ reputation
        if user.verified_reports_count >= 10 and user.reputation_score >= 70:
            old_role = user.role
            user.role = "verified_reporter"
            user.verified_reporter_since = datetime.utcnow()

            # Log role change to history
            role_history = models.RoleHistory(
                user_id=user.id,
                old_role=old_role,
                new_role="verified_reporter",
                changed_by=None,  # NULL indicates auto-promotion
                reason="Auto-promoted: 10+ verified reports with 70+ reputation score"
            )
            self.db.add(role_history)

            logger.info(f"User {user.id} auto-promoted to verified_reporter")
            return True

        return False
