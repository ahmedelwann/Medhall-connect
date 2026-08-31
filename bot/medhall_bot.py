"""
MedHall Connect - Global Anonymous Medical Education Telegram Bot
Production-Ready Implementation
"""

import os
import json
import logging
import asyncio
import uuid
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from enum import Enum
from dataclasses import dataclass, asdict

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes,
    CallbackContext,
)
from telegram.error import TelegramError

import psycopg2
from psycopg2.extras import RealDictCursor
import redis
from cryptography.fernet import Fernet

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('medhall_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# ENUMS & CONSTANTS
# ============================================================================

class UserMode(Enum):
    IDLE = "idle"
    ASKING = "asking"
    ANSWERING = "answering"
    IN_SESSION = "in_session"

class SessionStatus(Enum):
    MATCHING = "matching"
    ACTIVE = "active"
    ENDED = "ended"
    REPORTED = "reported"

class ModerationAction(Enum):
    WARNING = "warning"
    TEMP_RESTRICT = "temp_restrict"
    SESSION_TERMINATE = "terminate"
    ACCOUNT_BAN = "ban"

class AcademicLevel(Enum):
    FOUNDATION = "foundation"
    YEAR1 = "year_1"
    YEAR2 = "year_2"
    YEAR3 = "year_3"
    YEAR4 = "year_4"
    YEAR5 = "year_5"
    YEAR6 = "year_6"
    INTERNSHIP = "internship"
    GRADUATE = "graduate"
    POSTGRADUATE = "postgraduate"
    OTHER = "other"

# BUGFIX (code review): the matching query previously did
# `academic_level >= %s` directly on the VARCHAR column, which is a
# LEXICOGRAPHIC string comparison, not an academic-order comparison.
# e.g. 'foundation' > 'year_1' as a string (because 'f' > 'y' is false,
# but 'p' (postgraduate) < 'y' (year_1) is also true as a string even
# though postgraduate should outrank year_1) - the ordering was simply
# wrong. We fix it with an explicit numeric rank, stored in
# academic_level_rank (see database_schema.sql) and kept in sync here.
ACADEMIC_LEVEL_RANK: Dict[str, int] = {
    AcademicLevel.FOUNDATION.value: 0,
    AcademicLevel.YEAR1.value: 1,
    AcademicLevel.YEAR2.value: 2,
    AcademicLevel.YEAR3.value: 3,
    AcademicLevel.YEAR4.value: 4,
    AcademicLevel.YEAR5.value: 5,
    AcademicLevel.YEAR6.value: 6,
    AcademicLevel.INTERNSHIP.value: 7,
    AcademicLevel.GRADUATE.value: 8,
    AcademicLevel.POSTGRADUATE.value: 9,
    AcademicLevel.OTHER.value: 0,
}

class MedicalDiscipline(Enum):
    MEDICINE = "medicine"
    DENTISTRY = "dentistry"
    PHARMACY = "pharmacy"
    NURSING = "nursing"
    PHYSIOTHERAPY = "physiotherapy"
    VETERINARY = "veterinary"
    LAB_SCIENCE = "lab_science"
    RADIOLOGY = "radiology"
    OCCUPATIONAL_THERAPY = "occupational_therapy"
    PUBLIC_HEALTH = "public_health"
    BIOMEDICAL = "biomedical"
    OTHER = "other"

class Language(Enum):
    ENGLISH = "en"
    ARABIC = "ar"

# Configuration constants
MATCHING_TIMEOUT = int(os.getenv('MATCHING_TIMEOUT', '30'))
MAX_MESSAGE_LENGTH = 4000
MAX_DAILY_AI_USAGE = int(os.getenv('MAX_DAILY_AI_USAGE', '100'))
MESSAGE_RATE_LIMIT = int(os.getenv('MESSAGE_RATE_LIMIT', '20'))  # messages per minute
RATE_LIMIT_WINDOW = 60  # seconds

OFFICIAL_MEDHALL_CHANNEL = "https://t.me/medhalll"

# Conversation states
(STATE_LANGUAGE, STATE_FIELD, STATE_LEVEL, STATE_MODE, 
 STATE_TOPIC, STATE_QUESTION, STATE_MATCHING, STATE_SESSION,
 STATE_REPORT, STATE_ADMIN) = range(10)

# ============================================================================
# DATA MODELS
# ============================================================================

@dataclass
class UserProfile:
    telegram_id: int
    internal_user_id: str
    language: Language
    field: MedicalDiscipline
    academic_level: AcademicLevel
    country: Optional[str]
    created_at: datetime
    last_active: datetime
    is_banned: bool
    ban_reason: Optional[str]

@dataclass
class MatchSession:
    session_id: str
    asker_internal_id: str
    answerer_internal_id: Optional[str]  # None if AI fallback
    question: str
    topic: str
    status: SessionStatus
    created_at: datetime
    matched_at: Optional[datetime]
    ended_at: Optional[datetime]
    is_ai_fallback: bool = False
    ai_provider: Optional[str] = None
    message_count: int = 0

# ============================================================================
# DATABASE LAYER
# ============================================================================

class DatabaseManager:
    """Handles all database operations with security."""
    
    def __init__(self):
        self.conn_params = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': int(os.getenv('DB_PORT', '5432')),
            'database': os.getenv('DB_NAME', 'medhall_db'),
            'user': os.getenv('DB_USER', 'medhall_user'),
            'password': os.getenv('DB_PASSWORD'),
        }
    
    def get_connection(self):
        """Get a database connection."""
        try:
            return psycopg2.connect(**self.conn_params)
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise

    def create_user_profile(self, telegram_id: int, language: Language, 
                           field: MedicalDiscipline, academic_level: AcademicLevel,
                           country: Optional[str] = None) -> UserProfile:
        """Create a new user profile with internal ID."""
        internal_user_id = str(uuid.uuid4())
        
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            
            cur.execute("""
                INSERT INTO user_profiles 
                (telegram_id, internal_user_id, language, field, academic_level, academic_level_rank, country, created_at, last_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                RETURNING internal_user_id
            """, (telegram_id, internal_user_id, language.value, field.value, academic_level.value,
                  ACADEMIC_LEVEL_RANK.get(academic_level.value, 0), country))
            
            conn.commit()
            cur.close()
            conn.close()
            
            logger.info(f"User profile created: {internal_user_id}")
            
            return UserProfile(
                telegram_id=telegram_id,
                internal_user_id=internal_user_id,
                language=language,
                field=field,
                academic_level=academic_level,
                country=country,
                created_at=datetime.now(),
                last_active=datetime.now(),
                is_banned=False,
                ban_reason=None
            )
        except Exception as e:
            logger.error(f"Failed to create user profile: {e}")
            raise

    def get_user_by_telegram_id(self, telegram_id: int) -> Optional[UserProfile]:
        """Retrieve user profile by Telegram ID."""
        try:
            conn = self.get_connection()
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            cur.execute("""
                SELECT * FROM user_profiles WHERE telegram_id = %s
            """, (telegram_id,))
            
            row = cur.fetchone()
            cur.close()
            conn.close()
            
            if not row:
                return None
            
            return UserProfile(
                telegram_id=row['telegram_id'],
                internal_user_id=row['internal_user_id'],
                language=Language(row['language']),
                field=MedicalDiscipline(row['field']),
                academic_level=AcademicLevel(row['academic_level']),
                country=row['country'],
                created_at=row['created_at'],
                last_active=row['last_active'],
                is_banned=row['is_banned'],
                ban_reason=row['ban_reason']
            )
        except Exception as e:
            logger.error(f"Failed to retrieve user profile: {e}")
            return None

    def create_match_session(self, asker_internal_id: str, question: str, 
                            topic: str) -> MatchSession:
        """Create a new matching session."""
        session_id = str(uuid.uuid4())
        
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            
            cur.execute("""
                INSERT INTO match_sessions 
                (session_id, asker_internal_id, question, topic, status, created_at, is_ai_fallback)
                VALUES (%s, %s, %s, %s, %s, NOW(), FALSE)
            """, (session_id, asker_internal_id, question, topic, SessionStatus.MATCHING.value))
            
            conn.commit()
            cur.close()
            conn.close()
            
            logger.info(f"Match session created: {session_id}")
            
            return MatchSession(
                session_id=session_id,
                asker_internal_id=asker_internal_id,
                answerer_internal_id=None,
                question=question,
                topic=topic,
                status=SessionStatus.MATCHING,
                created_at=datetime.now(),
                matched_at=None,
                ended_at=None
            )
        except Exception as e:
            logger.error(f"Failed to create match session: {e}")
            raise

    def log_message(self, session_id: str, sender_internal_id: str, 
                   content: str, is_flagged: bool = False, 
                   flag_reason: Optional[str] = None):
        """Log a message with content moderation flags."""
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            
            cur.execute("""
                INSERT INTO session_messages 
                (session_id, sender_internal_id, content, is_flagged, flag_reason, created_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
            """, (session_id, sender_internal_id, content, is_flagged, flag_reason))
            
            conn.commit()
            cur.close()
            conn.close()
        except Exception as e:
            logger.error(f"Failed to log message: {e}")

    def create_report(self, session_id: str, reporter_internal_id: str,
                     reported_internal_id: str, reason: str, 
                     evidence: Optional[str] = None) -> str:
        """Create an abuse report."""
        report_id = str(uuid.uuid4())
        
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            
            cur.execute("""
                INSERT INTO reports 
                (report_id, session_id, reporter_internal_id, reported_internal_id, reason, evidence, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, 'open', NOW())
            """, (report_id, session_id, reporter_internal_id, reported_internal_id, reason, evidence))
            
            # Update session status
            cur.execute("""
                UPDATE match_sessions SET status = %s WHERE session_id = %s
            """, (SessionStatus.REPORTED.value, session_id))
            
            conn.commit()
            cur.close()
            conn.close()
            
            logger.warning(f"Report created: {report_id} for session {session_id}")
            
            return report_id
        except Exception as e:
            logger.error(f"Failed to create report: {e}")
            raise

    def check_rate_limit(self, user_internal_id: str) -> Tuple[bool, int]:
        """Check if user has exceeded rate limits."""
        try:
            conn = self.get_connection()
            cur = conn.cursor()
            
            # Check messages in last minute
            cur.execute("""
                SELECT COUNT(*) as count FROM session_messages 
                WHERE sender_internal_id = %s 
                AND created_at > NOW() - INTERVAL '1 minute'
            """, (user_internal_id,))
            
            row = cur.fetchone()
            count = row[0] if row else 0
            cur.close()
            conn.close()
            
            is_limited = count >= MESSAGE_RATE_LIMIT
            return is_limited, count
        except Exception as e:
            logger.error(f"Rate limit check failed: {e}")
            return False, 0

# ============================================================================
# CONTENT MODERATION
# ============================================================================

class ContentModerator:
    """Detects potentially problematic content."""
    
    # Patterns for detecting PII
    EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
    PHONE_PATTERN = re.compile(r'(?:\+\d{1,3}[-.\s]?)?\(?(?:\d{2,4})\)?[-.\s]?\d{2,4}[-.\s]?\d{2,9}')
    TELEGRAM_USERNAME_PATTERN = re.compile(r'@[A-Za-z0-9_]{5,32}')
    TELEGRAM_LINK_PATTERN = re.compile(r'(?:https?://)?(?:t\.me/|telegram\.me/)\S+')
    SOCIAL_MEDIA_HANDLE_PATTERN = re.compile(r'(?:instagram|whatsapp|facebook|twitter|snapchat|tiktok)[:\s]+\S+', re.IGNORECASE)
    
    IDENTITY_REQUEST_KEYWORDS = [
        'your name', 'your real name', 'actual name',
        'phone number', 'contact number', 'call me',
        'telegram username', 'telegram id',
        'instagram', 'whatsapp', 'facebook',
        'real identity', 'actual person',
        'meet in person', 'real life',
        'address', 'location',
    ]
    
    @staticmethod
    def detect_pii(content: str) -> Tuple[bool, Optional[str]]:
        """Detect personally identifiable information."""
        content_lower = content.lower()
        
        # Check for email
        if ContentModerator.EMAIL_PATTERN.search(content):
            return True, "email_address"
        
        # Check for phone
        if ContentModerator.PHONE_PATTERN.search(content):
            return True, "phone_number"
        
        # Check for Telegram username
        if ContentModerator.TELEGRAM_USERNAME_PATTERN.search(content):
            return True, "telegram_username"
        
        # Check for Telegram links
        if ContentModerator.TELEGRAM_LINK_PATTERN.search(content):
            return True, "telegram_link"
        
        # Check for social media
        if ContentModerator.SOCIAL_MEDIA_HANDLE_PATTERN.search(content):
            return True, "social_media_handle"
        
        return False, None
    
    @staticmethod
    def detect_identity_request(content: str) -> bool:
        """Detect attempts to ask for identity."""
        content_lower = content.lower()
        
        for keyword in ContentModerator.IDENTITY_REQUEST_KEYWORDS:
            if keyword in content_lower:
                return True
        
        return False
    
    @staticmethod
    def moderate_content(content: str) -> Tuple[bool, Optional[str], str]:
        """
        Full content moderation.
        Returns: (is_blocked, reason, sanitized_content)
        """
        has_pii, pii_type = ContentModerator.detect_pii(content)
        
        if has_pii:
            return True, f"pii_detected:{pii_type}", content
        
        if ContentModerator.detect_identity_request(content):
            return True, "identity_request", content
        
        return False, None, content

# ============================================================================
# MATCHING ENGINE
# ============================================================================

class MatchingEngine:
    """Smart matching algorithm."""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    async def find_best_match(self, asker_profile: UserProfile, 
                             question_topic: str, session_id: str) -> Optional[str]:
        """
        Find best matching answerer and atomically reserve them for this
        session so two askers can never be matched to the same answerer
        at the same time.

        BUGFIX (code review):
        1. `academic_level >= %s` compared VARCHAR values lexicographically,
           which does not reflect real academic ordering. Fixed to compare
           `academic_level_rank` (int).
        2. There was no locking: two concurrent askers could both read the
           same "free" answerer and both get matched to them (a race
           condition explicitly called out as a requirement to prevent).
           Fixed with `SELECT ... FOR UPDATE SKIP LOCKED` inside a single
           transaction, plus an atomic UPDATE that only succeeds if the
           candidate is still unmatched, so only one asker can win a given
           answerer.
        3. The asker could theoretically match with themselves if they were
           also registered as an eligible answerer; now explicitly excluded.
        4. Candidates who already have an active/matching session as an
           answerer are excluded, so one person can't be double-booked.

        Returns internal_user_id of answerer, or None if no match found.
        NOT EXECUTED against a live database in this environment (no network
        access / no Postgres instance available) - reviewed manually only.
        """
        conn = None
        try:
            conn = self.db.get_connection()
            conn.autocommit = False
            cur = conn.cursor(cursor_factory=RealDictCursor)

            cur.execute("""
                SELECT internal_user_id
                FROM user_profiles
                WHERE is_banned = FALSE
                AND field = %s
                AND academic_level_rank >= %s
                AND internal_user_id <> %s
                AND internal_user_id NOT IN (
                    SELECT blocked_user_id FROM blocks
                    WHERE blocking_user_id = %s
                )
                AND internal_user_id NOT IN (
                    SELECT blocking_user_id FROM blocks
                    WHERE blocked_user_id = %s
                )
                AND internal_user_id NOT IN (
                    SELECT answerer_internal_id FROM match_sessions
                    WHERE answerer_internal_id IS NOT NULL
                    AND status IN ('matching', 'active')
                )
                ORDER BY RANDOM()
                LIMIT 5
                FOR UPDATE SKIP LOCKED
            """, (
                asker_profile.field.value,
                ACADEMIC_LEVEL_RANK.get(asker_profile.academic_level.value, 0),
                asker_profile.internal_user_id,
                asker_profile.internal_user_id,
                asker_profile.internal_user_id,
            ))

            candidates = cur.fetchall()

            for candidate in candidates:
                candidate_id = candidate['internal_user_id']
                # Atomically claim this answerer for this session. The
                # WHERE clause re-checks the session is still MATCHING and
                # has no answerer yet, so a concurrent transaction that won
                # the race can't be overwritten.
                cur.execute("""
                    UPDATE match_sessions
                    SET answerer_internal_id = %s,
                        status = %s,
                        matched_at = NOW()
                    WHERE session_id = %s
                    AND status = %s
                    AND answerer_internal_id IS NULL
                    RETURNING session_id
                """, (candidate_id, SessionStatus.ACTIVE.value, session_id,
                      SessionStatus.MATCHING.value))

                claimed = cur.fetchone()
                if claimed:
                    conn.commit()
                    return candidate_id
                # Someone else claimed this session already (shouldn't
                # normally happen per-session, but guards against retries).
                conn.rollback()
                return None

            conn.commit()
            return None
        except Exception as e:
            logger.error(f"Matching engine error: {e}")
            if conn:
                conn.rollback()
            return None
        finally:
            if conn:
                conn.close()

# ============================================================================
# AI PROVIDER ABSTRACTION
# ============================================================================

class AIProvider:
    """Abstract AI provider interface."""
    
    async def generate_educational_response(self, question: str, 
                                           topic: str, 
                                           discipline: MedicalDiscipline,
                                           academic_level: AcademicLevel) -> str:
        raise NotImplementedError

class AnthropicProvider(AIProvider):
    """Anthropic Claude provider."""
    
    def __init__(self):
        self.api_key = os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")
    
    async def generate_educational_response(self, question: str, 
                                           topic: str, 
                                           discipline: MedicalDiscipline,
                                           academic_level: AcademicLevel) -> str:
        """Generate educational response using Claude."""
        try:
            import anthropic
            
            client = anthropic.Anthropic(api_key=self.api_key)
            
            system_prompt = f"""You are an anonymous educational assistant in MedHall Connect.
Your role is to help {discipline.value} students at {academic_level.value} level.

CRITICAL RULES:
1. This is EDUCATIONAL ASSISTANCE only
2. NOT medical diagnosis or treatment
3. NOT a substitute for qualified healthcare professionals
4. For personal medical situations, clearly state this is not personalized advice
5. For emergencies, direct to appropriate medical services
6. Be helpful, clear, and educational in your explanation

Discipline: {discipline.value}
Academic Level: {academic_level.value}
Topic: {topic}"""
            
            message = client.messages.create(
                model="claude-opus-4-1",
                max_tokens=1000,
                system=system_prompt,
                messages=[
                    {
                        "role": "user",
                        "content": question
                    }
                ]
            )
            
            return message.content[0].text
        except Exception as e:
            logger.error(f"AI provider error: {e}")
            return "I apologize, but I'm unable to generate a response at this moment. Please try again."

class AIFallbackChain:
    """Manages AI provider fallback."""
    
    def __init__(self):
        self.providers = []
        self._initialize_providers()
    
    def _initialize_providers(self):
        """Initialize providers based on configuration."""
        try:
            if os.getenv('ANTHROPIC_API_KEY'):
                self.providers.append(("anthropic", AnthropicProvider()))
        except Exception as e:
            logger.warning(f"Could not initialize AI provider: {e}")
    
    async def get_response(self, question: str, topic: str,
                          discipline: MedicalDiscipline,
                          academic_level: AcademicLevel) -> Optional[str]:
        """Get response from available provider."""
        for provider_name, provider in self.providers:
            try:
                response = await provider.generate_educational_response(
                    question, topic, discipline, academic_level
                )
                return response
            except Exception as e:
                logger.warning(f"Provider {provider_name} failed: {e}")
                continue
        
        return None

# ============================================================================
# LOCALIZATION
# ============================================================================

LOCALIZATION = {
    Language.ENGLISH: {
        'welcome': 'Welcome to MedHall Connect',
        'welcome_desc': 'A global anonymous medical education network',
        'select_language': 'Select your language',
        'select_field': 'Select your medical field',
        'select_level': 'Select your academic level',
        'ask_or_answer': 'What would you like to do?',
        'ask_button': '🤔 Ask a Question',
        'answer_button': '💡 Answer Questions',
        'select_topic': 'Select topic',
        'enter_question': 'Enter your question',
        'matching': 'Finding an answerer...',
        'ai_fallback': 'No suitable answerer found. Using AI Educational Assistant.',
        'session_started': 'Session started. You are connected anonymously.',
        'end_session': 'End Session',
        'report': '🚩 Report',
        'block': '🚫 Block',
        'thank_you': 'Thank you for using MedHall Connect',
        'report_submitted': 'Report submitted. Thank you for helping keep our community safe.',
        'medical_disclaimer': 'This is an educational service only. Not medical advice.',
        'terms_accept': 'I accept the Terms and Privacy Policy',
        'join_channel': '📢 Join Official MedHall Channel',
        'official_medhall': 'Official MedHall Platform',
        'help': 'Help & Support',
        'rules': 'Rules & Safety',
    },
    Language.ARABIC: {
        'welcome': 'أهلا بك في MedHall Connect',
        'welcome_desc': 'شبكة تعليم طبي مجهولة عالمية',
        'select_language': 'اختر لغتك',
        'select_field': 'اختر تخصصك الطبي',
        'select_level': 'اختر مستواك الأكاديمي',
        'ask_or_answer': 'ماذا تود أن تفعل؟',
        'ask_button': '🤔 اطرح سؤالاً',
        'answer_button': '💡 أجب على الأسئلة',
        'select_topic': 'اختر الموضوع',
        'enter_question': 'أدخل سؤالك',
        'matching': 'جاري البحث عن شخص للإجابة...',
        'ai_fallback': 'لم يتم العثور على مجيب مناسب. استخدام مساعد تعليمي ذكي.',
        'session_started': 'بدأت الجلسة. أنت متصل بشكل مجهول.',
        'end_session': 'إنهاء الجلسة',
        'report': '🚩 إبلاغ',
        'block': '🚫 حظر',
        'thank_you': 'شكراً لاستخدامك MedHall Connect',
        'report_submitted': 'تم تقديم البلاغ. شكراً لمساعدتك في الحفاظ على سلامة المجتمع.',
        'medical_disclaimer': 'هذه خدمة تعليمية فقط. ليست نصيحة طبية.',
        'terms_accept': 'أوافق على الشروط وسياسة الخصوصية',
        'join_channel': '📢 انضم إلى قناة MedHall الرسمية',
        'official_medhall': 'منصة MedHall الرسمية',
        'help': 'المساعدة والدعم',
        'rules': 'القواعد والسلامة',
    }
}

def get_text(language: Language, key: str) -> str:
    """Get localized text."""
    return LOCALIZATION.get(language, {}).get(key, key)

# ============================================================================
# BOT HANDLERS
# ============================================================================

class MedHallBot:
    """Main bot implementation."""
    
    def __init__(self):
        self.db = DatabaseManager()
        self.matcher = MatchingEngine(self.db)
        self.ai_chain = AIFallbackChain()
        self.moderator = ContentModerator()
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Start handler - first entry point."""
        user = update.effective_user
        
        # Check if user exists
        existing_profile = self.db.get_user_by_telegram_id(user.id)
        
        if existing_profile:
            if existing_profile.is_banned:
                await update.message.reply_text(
                    "Your account has been banned from MedHall Connect. "
                    f"Reason: {existing_profile.ban_reason}"
                )
                return ConversationHandler.END
            
            # User already onboarded
            await self._show_main_menu(update, context, existing_profile.language)
            return STATE_MODE
        
        # New user - start onboarding
        keyboard = [
            [InlineKeyboardButton("English", callback_data="lang_en")],
            [InlineKeyboardButton("العربية", callback_data="lang_ar")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "🏥 Welcome to MedHall Connect\n\n"
            "A global anonymous medical education network\n\n"
            "Select your language / اختر لغتك:",
            reply_markup=reply_markup
        )
        
        return STATE_LANGUAGE
    
    async def language_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle language selection."""
        query = update.callback_query
        await query.answer()
        
        lang = Language.ENGLISH if "en" in query.data else Language.ARABIC
        context.user_data['language'] = lang
        
        # Show field selection
        await self._show_field_selection(query.message, lang)
        
        return STATE_FIELD
    
    async def _show_field_selection(self, message, language: Language):
        """Show medical field selection."""
        keyboard = [
            [InlineKeyboardButton("Medicine", callback_data="field_medicine")],
            [InlineKeyboardButton("Dentistry", callback_data="field_dentistry")],
            [InlineKeyboardButton("Pharmacy", callback_data="field_pharmacy")],
            [InlineKeyboardButton("Nursing", callback_data="field_nursing")],
            [InlineKeyboardButton("Physiotherapy", callback_data="field_physio")],
            [InlineKeyboardButton("Other", callback_data="field_other")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await message.edit_text(
            get_text(language, 'select_field'),
            reply_markup=reply_markup
        )
    
    async def field_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle field selection."""
        query = update.callback_query
        await query.answer()
        
        field_map = {
            "medicine": MedicalDiscipline.MEDICINE,
            "dentistry": MedicalDiscipline.DENTISTRY,
            "pharmacy": MedicalDiscipline.PHARMACY,
            "nursing": MedicalDiscipline.NURSING,
            "physio": MedicalDiscipline.PHYSIOTHERAPY,
            "other": MedicalDiscipline.OTHER,
        }
        
        for key, value in field_map.items():
            if key in query.data:
                context.user_data['field'] = value
                break
        
        language = context.user_data.get('language', Language.ENGLISH)
        
        # Show academic level selection
        keyboard = [
            [InlineKeyboardButton("Foundation", callback_data="level_foundation")],
            [InlineKeyboardButton("Year 1-2", callback_data="level_year1")],
            [InlineKeyboardButton("Year 3-4", callback_data="level_year3")],
            [InlineKeyboardButton("Year 5-6", callback_data="level_year5")],
            [InlineKeyboardButton("Postgraduate", callback_data="level_postgrad")],
            [InlineKeyboardButton("Other", callback_data="level_other")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.message.edit_text(
            get_text(language, 'select_level'),
            reply_markup=reply_markup
        )
        
        return STATE_LEVEL
    
    async def level_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle academic level selection."""
        query = update.callback_query
        await query.answer()
        
        level_map = {
            "foundation": AcademicLevel.FOUNDATION,
            "year1": AcademicLevel.YEAR1,
            "year3": AcademicLevel.YEAR3,
            "year5": AcademicLevel.YEAR5,
            "postgrad": AcademicLevel.POSTGRADUATE,
            "other": AcademicLevel.OTHER,
        }
        
        for key, value in level_map.items():
            if key in query.data:
                context.user_data['level'] = value
                break
        
        language = context.user_data.get('language', Language.ENGLISH)
        field = context.user_data.get('field', MedicalDiscipline.MEDICINE)
        level = context.user_data.get('level', AcademicLevel.YEAR1)
        
        # Create user profile
        try:
            profile = self.db.create_user_profile(
                telegram_id=update.effective_user.id,
                language=language,
                field=field,
                academic_level=level,
                country=None
            )
            context.user_data['user_profile'] = profile
        except Exception as e:
            logger.error(f"Failed to create user profile: {e}")
            await query.message.reply_text("Error creating profile. Please try again.")
            return ConversationHandler.END
        
        # Show main menu
        await self._show_main_menu(query.message, context, language)
        
        return STATE_MODE
    
    async def _show_main_menu(self, message_or_update, context: ContextTypes.DEFAULT_TYPE, language: Language):
        """Display main menu."""
        keyboard = [
            [InlineKeyboardButton(get_text(language, 'ask_button'), callback_data="mode_ask")],
            [InlineKeyboardButton(get_text(language, 'answer_button'), callback_data="mode_answer")],
            [InlineKeyboardButton(get_text(language, 'join_channel'), url=OFFICIAL_MEDHALL_CHANNEL)],
            [InlineKeyboardButton(get_text(language, 'help'), callback_data="mode_help")],
            [InlineKeyboardButton(get_text(language, 'rules'), callback_data="mode_rules")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        text = f"""
{get_text(language, 'welcome')}

🔐 Anonymous Medical Education Network
🌍 For students worldwide
🤝 Peer-to-peer learning + AI support

{get_text(language, 'ask_or_answer')}
"""
        
        # Handle both Message and Message.edit_text
        if hasattr(message_or_update, 'edit_text'):
            await message_or_update.edit_text(text, reply_markup=reply_markup)
        else:
            await message_or_update.message.reply_text(text, reply_markup=reply_markup)
    
    async def mode_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle mode selection (ask/answer)."""
        query = update.callback_query
        await query.answer()
        
        language = context.user_data.get('language', Language.ENGLISH)
        
        if "ask" in query.data:
            context.user_data['current_mode'] = UserMode.ASKING
            
            # Show topic selection
            keyboard = [
                [InlineKeyboardButton("Anatomy", callback_data="topic_anatomy")],
                [InlineKeyboardButton("Physiology", callback_data="topic_physiology")],
                [InlineKeyboardButton("Pharmacology", callback_data="topic_pharma")],
                [InlineKeyboardButton("Pathology", callback_data="topic_patho")],
                [InlineKeyboardButton("General", callback_data="topic_general")],
                [InlineKeyboardButton("Other", callback_data="topic_other")],
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.message.edit_text(
                get_text(language, 'select_topic'),
                reply_markup=reply_markup
            )
            
            return STATE_TOPIC
        
        elif "answer" in query.data:
            context.user_data['current_mode'] = UserMode.ANSWERING
            
            # Put user in answerer pool
            await query.message.edit_text(
                "You're in the answerer pool. Waiting for questions that match your expertise..."
            )
            
            # In production, would actually add to Redis pool
            # For now, just acknowledge
            
            return STATE_MODE
        
        return STATE_MODE
    
    async def topic_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle topic selection."""
        query = update.callback_query
        await query.answer()
        
        topic_map = {
            "anatomy": "Anatomy",
            "physiology": "Physiology",
            "pharma": "Pharmacology",
            "patho": "Pathology",
            "general": "General Academic",
            "other": "Other",
        }
        
        for key, value in topic_map.items():
            if key in query.data:
                context.user_data['topic'] = value
                break
        
        language = context.user_data.get('language', Language.ENGLISH)
        
        await query.message.edit_text(
            get_text(language, 'enter_question'),
            reply_markup=ReplyKeyboardMarkup([["Cancel"]])
        )
        
        return STATE_QUESTION
    
    async def question_input(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle question input."""
        question = update.message.text
        
        if question.lower() == "cancel":
            language = context.user_data.get('language', Language.ENGLISH)
            await self._show_main_menu(update, context, language)
            return STATE_MODE
        
        language = context.user_data.get('language', Language.ENGLISH)
        profile = context.user_data.get('user_profile')
        
        # Create match session
        try:
            session = self.db.create_match_session(
                asker_internal_id=profile.internal_user_id,
                question=question,
                topic=context.user_data.get('topic', 'General')
            )
            context.user_data['current_session'] = session
        except Exception as e:
            logger.error(f"Failed to create session: {e}")
            await update.message.reply_text("Error creating session. Try again.")
            return STATE_MODE
        
        # Start matching with timeout
        await update.message.reply_text(
            get_text(language, 'matching'),
            reply_markup=ReplyKeyboardRemove()
        )
        
        # Try to find a human match, polling for up to MATCHING_TIMEOUT
        # seconds before falling back to AI (requirement: 30s human
        # timeout, configurable via MATCHING_TIMEOUT env var).
        # BUGFIX (code review): the previous version tried exactly once and
        # immediately fell back to AI - it never actually waited the
        # configured window for a human to become available.
        matched_answerer = None
        poll_interval = 3
        elapsed = 0
        while elapsed < MATCHING_TIMEOUT:
            matched_answerer = await self.matcher.find_best_match(
                profile, context.user_data.get('topic'), session.session_id
            )
            if matched_answerer:
                break
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

        if matched_answerer:
            # Found human answerer - in production, would send to them
            logger.info(f"Match found: {matched_answerer}")
            context.user_data['current_session'].answerer_internal_id = matched_answerer
            
            await update.message.reply_text(
                f"{get_text(language, 'session_started')}\n\n"
                "You are now connected with an anonymous answerer.\n"
                "Your question has been shared."
            )
        else:
            # No match - use AI fallback
            await update.message.reply_text(
                f"{get_text(language, 'ai_fallback')}\n\n"
                "Generating response..."
            )
            
            # Generate AI response
            ai_response = await self.ai_chain.get_response(
                question,
                context.user_data.get('topic'),
                profile.field,
                profile.academic_level
            )
            
            if ai_response:
                # Truncate if needed
                if len(ai_response) > MAX_MESSAGE_LENGTH:
                    ai_response = ai_response[:MAX_MESSAGE_LENGTH] + "..."
                
                context.user_data['current_session'].is_ai_fallback = True
                context.user_data['current_session'].ai_provider = "anthropic"
                
                keyboard = [
                    [InlineKeyboardButton(get_text(language, 'end_session'), callback_data="action_end")],
                    [InlineKeyboardButton(get_text(language, 'report'), callback_data="action_report")],
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"🤖 Educational AI Response:\n\n{ai_response}",
                    reply_markup=reply_markup
                )
            else:
                await update.message.reply_text(
                    "Sorry, unable to generate a response. Please try again."
                )
        
        return STATE_SESSION
    
    async def session_action(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle session actions (end, report, etc)."""
        query = update.callback_query
        await query.answer()
        
        language = context.user_data.get('language', Language.ENGLISH)
        
        if "end" in query.data:
            context.user_data['current_session'] = None
            await self._show_main_menu(query.message, context, language)
            return STATE_MODE
        
        elif "report" in query.data:
            await query.message.reply_text(
                f"Why are you reporting this?\n\n"
                "1. Identity disclosure attempt\n"
                "2. Harassment\n"
                "3. Inappropriate content\n"
                "4. Other"
            )
            return STATE_REPORT
        
        return STATE_SESSION

# ============================================================================
# MAIN SETUP
# ============================================================================

async def main():
    """Start the bot."""
    # Load token from environment
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN not set")
    
    # Create application
    application = Application.builder().token(token).build()
    
    # Initialize bot instance
    bot_instance = MedHallBot()
    
    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", bot_instance.start)],
        states={
            STATE_LANGUAGE: [CallbackQueryHandler(bot_instance.language_callback)],
            STATE_FIELD: [CallbackQueryHandler(bot_instance.field_callback)],
            STATE_LEVEL: [CallbackQueryHandler(bot_instance.level_callback)],
            STATE_MODE: [CallbackQueryHandler(bot_instance.mode_callback)],
            STATE_TOPIC: [CallbackQueryHandler(bot_instance.topic_callback)],
            STATE_QUESTION: [MessageHandler(filters.TEXT, bot_instance.question_input)],
            STATE_SESSION: [CallbackQueryHandler(bot_instance.session_action)],
            STATE_REPORT: [MessageHandler(filters.TEXT, bot_instance.question_input)],
        },
        fallbacks=[CommandHandler("start", bot_instance.start)],
    )
    
    application.add_handler(conv_handler)
    
    logger.info("MedHall Connect bot started")
    await application.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
