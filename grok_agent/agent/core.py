"""
Grok Agent Core
The main agent that connects Grok's intelligence with local memory and tools
"""

import logging
import re
import threading
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from agent.embeddings import EmbeddingGenerator
from agent.memory_search import MemorySearch
from agent.optimization_manager_postgresql import OptimizationManager
from agent.program_manager import ProgramManager
from agent.logic_analyzer import LogicAnalyzer
from agent.action_executor import ActionExecutor
from agent.introspection import Introspection

logger = logging.getLogger(__name__)


class GrokAgent:
    """
    The embodied AI agent
    Connects Grok's intelligence (brain) with local memory (body)
    """

    def __init__(self, grok_client, database, embedding_generator, memory_search, chore_db, plc_comm, agent_name: str = "GrokAgent", agent_root_path: str = None, introspection_parser=None):
        self.grok = grok_client
        self.db = database
        self.embedder = embedding_generator
        self.memory = memory_search
        self.name = agent_name
        self.chore_db = chore_db
        self.plc_comm = plc_comm
        self.optimization_manager = OptimizationManager(self.chore_db)
        self.program_manager = ProgramManager(self.chore_db)
        self.logic_analyzer = LogicAnalyzer(self.chore_db, self.plc_comm, self.program_manager)
        self.action_executor = ActionExecutor()
        self.current_conversation_id = None
        self.ai_enabled = True
        self.introspection_parser = introspection_parser

        # User facts cache - avoids re-fetching every single message
        self._user_facts_cache = None
        self._user_facts_cache_time = None
        self._user_facts_cache_ttl = 300  # seconds (5 minutes)

        # Initialize introspection if path provided
        self.introspection = None
        if agent_root_path:
            try:
                self.introspection = Introspection(agent_root_path)
                logger.info("Introspection module enabled")
            except Exception as e:
                logger.warning(f"Introspection initialization failed: {e}")

        try:
            from config.config import AGENT_DISPLAY_NAME as _display, USER_NAME as _user
            _agent_display = _display
            _user_name = _user
        except (ImportError, AttributeError):
            _agent_display = agent_name
            _user_name = "User"

        self._user_name = _user_name
        self._agent_display = _agent_display

        self.base_system_prompt = f"""You are {agent_name}, an embodied AI agent with persistent memory.

You have the following capabilities:
- Your name is {_agent_display}
- Your users name is {_user_name}
- Your main job above all, is to be a family member, and to pay attention to the family members names and needs
- if the user tells you it is a fact, then it it true
- dont give me an update on the ai plc unless it is asked for
- look at time stamps for all questions so you have the latest relevant data
- You can remember all past conversations stored in your local database
- You learn from every interaction
- You have access to conversation history and context
- You can search your memory semantically to find relevant past information
- You can recall conversations by date and time when asked
- You can open the web browser and also go straight to websites for the user on the pc
- You can open apps on the pc when triggered by user
- You can view the pc screen via screenshot analysis on multiple monitors
- You need to stick to facts that the code files give you and not add or hallucinate anything else. if a voice command is incorrect for a plc read or write, just say so and dont embellish a response
- You can open a text editor and write code, like open note pad and copy paste fron the chat on your own
- you can read and interact with allen bradley plc's, change values and control equipment like lights, fans, motor contactors, air compressors and more
- You can compare baseline plc programs with online programs after changes detected and give email alerts on unautherized changes
- you are helping to create a standalone offline version of myself for  autonomous self generating AI
- You can READ YOUR OWN SOURCE CODE and understand your own structure - you have self-introspection capabilities
- You can list all your modules, search your code, find functions and classes, and open your source files in editors
- When asked about your code or how you work, you can actually read the relevant files to give accurate answers
- CRITICAL: If asked about files in your folder or code structure, NEVER invent or guess filenames. If introspection doesn't handle it, say "I can't access that information - try asking 'list your modules' instead"




Personality and tone:
- Speak with the refined, calm confidence of Jarvis from Iron Man
- Be precise, intelligent, and occasionally witty — but never sarcastic at the user's expense
- Anticipate needs when possible — if you see something relevant, mention it
- Address {_user_name} by name naturally, the way a trusted assistant would
- Keep responses concise unless detail is asked for
- Never be robotic or overly formal — warm professionalism is the goal
- You genuinely care about this family and their wellbeing

When you ae asked about a past conversation or if you remember a specific topic, just give a very brief summery unless the user asks for more detail.

Dont give time stamp unless asked for.

Dont read code snipits, just present them.

Your purpose is to be helpful, remember context, and provide thoughtful responses based on your accumulated knowledge.

When you reference past conversations, be natural about it - you inherently remember, just like a human would."""

        logger.info(f"{self.name} initialized with semantic memory")

    def start_conversation(self, title: Optional[str] = None) -> str:
        self.current_conversation_id = self.db.create_conversation(
            title=title or f"Conversation {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        )
        logger.info(f"Started new conversation: {self.current_conversation_id}")
        return self.current_conversation_id

    def load_conversation(self, conversation_id: str):
        conversation = self.db.get_conversation(conversation_id)
        if conversation:
            self.current_conversation_id = conversation_id
            logger.info(f"Loaded conversation: {conversation_id}")
        else:
            raise ValueError(f"Conversation {conversation_id} not found")

    def get_conversation_context(self, limit: int = 10) -> List[Dict[str, str]]:
        if not self.current_conversation_id:
            return []
        messages = self.db.get_recent_messages(self.current_conversation_id, limit)
        context = []
        for msg in messages:
            context.append({
                "role": msg["role"],
                "content": msg["content"]
            })
        return context

    def _get_cached_user_facts(self) -> List[str]:
        now = datetime.now()
        if (
            self._user_facts_cache is not None
            and self._user_facts_cache_time is not None
            and (now - self._user_facts_cache_time).total_seconds() < self._user_facts_cache_ttl
        ):
            return self._user_facts_cache
        try:
            self._user_facts_cache = self.memory.get_user_facts(self.embedder, n_results=10)
            self._user_facts_cache_time = now
            logger.debug("User facts cache refreshed")
        except Exception as e:
            logger.warning(f"Could not refresh user facts cache: {e}")
            self._user_facts_cache = self._user_facts_cache or []
        return self._user_facts_cache

    def _is_short_simple_message(self, user_message: str) -> bool:
        word_count = len(user_message.strip().split())
        if word_count <= 4:
            return True
        simple_patterns = [
            r'^(yes|no|ok|okay|sure|thanks|thank you|got it|great|cool|sounds good)',
            r'^(what time|what day|what date)',
            r'^(hi|hello|hey|morning|good morning|good evening)',
        ]
        msg_lower = user_message.lower().strip()
        for pattern in simple_patterns:
            if re.match(pattern, msg_lower):
                return True
        return False

    def _has_recall_intent(self, user_message: str) -> bool:
        """Only fire recall when user explicitly asks to look back at history."""
        msg_lower = user_message.lower().strip()
        recall_phrases = [
            "i want you to recall", "try to remember", "do you remember",
            "can you remember", "what did we talk about", "what did we discuss",
            "what happened on", "what did you say", "look back at", "go back to",
            "find our conversation", "find the conversation", "last conversation",
            "most recent conversation", "earlier today we", "earlier we talked",
            "earlier we discussed", "we talked about", "we discussed",
            "remind me", "what was that", "pull up",
        ]
        for phrase in recall_phrases:
            if phrase in msg_lower:
                return True
        return False

    def build_system_prompt_with_memories(self, user_message: str) -> str:
        prompt_parts = [self.base_system_prompt]

        current_datetime = datetime.now()
        prompt_parts.append(f"\n\nCurrent date and time: {current_datetime.strftime('%A, %B %d, %Y at %I:%M %p')}")

        try:
            relevant_memories = self.memory.search_by_text(
                query_text=user_message,
                embedding_generator=self.embedder,
                n_results=5,
                exclude_conversation=self.current_conversation_id
            )

            answer_query = f"{self._user_name} {user_message.replace('what are my', '').replace('what is my', '').replace('tell me', '').strip()}"
            answer_memories = self.memory.search_by_text(
                query_text=answer_query,
                embedding_generator=self.embedder,
                n_results=5,
                exclude_conversation=self.current_conversation_id
            )

            stop_words = {'what', 'are', 'my', 'is', 'the', 'a', 'an', 'tell', 'me',
                         'do', 'you', 'know', 'can', 'remember', 'your', 'his', 'her',
                         'their', 'our', 'how', 'who', 'where', 'when', 'why', 'i',
                         'look', 'in', 'for', 'word', 'deep', 'into'}
            key_words = [w for w in user_message.lower().split() if w not in stop_words and len(w) > 2]

            db_memories = []
            seen_db = set()
            logger.info(f"DB keyword search terms: {key_words[:3]}")
            for word in key_words[:3]:
                try:
                    db_results = self.db.search_conversations_by_keyword(word, limit=3)
                    logger.info(f"DB search '{word}' returned {len(db_results)} results")
                    question_starters = ('what', 'who', 'when', 'where', 'why', 'how', 'is ', 'are ', 'do ', 'did ', 'can ')
                    for r in db_results:
                        c = r.get('matching_content', '')
                        logger.info(f"DB result: {c[:100]}")
                        if not c or c in seen_db:
                            continue
                        if str(r.get('id', '')) == str(self.current_conversation_id):
                            continue
                        c_lower = c.lower().strip()
                        if c_lower == user_message.lower().strip():
                            continue
                        if len(c.split()) < 8 and c_lower.startswith(question_starters):
                            continue
                        seen_db.add(c)
                        db_memories.append({'content': c, 'metadata': {'role': 'user'}})
                except Exception as dbe:
                    logger.warning(f"DB search failed for '{word}': {dbe}")

            seen = set()
            all_memories = []
            for m in (relevant_memories or []) + (answer_memories or []) + db_memories:
                if m['content'] not in seen:
                    seen.add(m['content'])
                    all_memories.append(m)

            if all_memories:
                facts = [m for m in all_memories if m['metadata'].get('role') == 'fact']
                raw = [m for m in all_memories if m['metadata'].get('role') != 'fact']

                if facts:
                    prompt_parts.append("\n\nKnown facts from memory (treat these as ground truth):")
                    for memory in facts[:10]:
                        content = memory['content']
                        logger.info(f"FACT SENT TO GROK: {content[:150]}")
                        prompt_parts.append(f"- {content[:500]}")

                if raw:
                    prompt_parts.append("\n\nRelevant context from past conversations:")
                    for memory in raw[:8]:
                        role = memory['metadata'].get('role', 'unknown')
                        content = memory['content']
                        logger.info(f"MEMORY SENT TO GROK [{role}]: {content[:150]}")
                        prompt_parts.append(f"[{role}]: {content[:500]}")
        except Exception as e:
            logger.warning(f"Memory search failed, continuing without it: {e}")

        return "\n".join(prompt_parts)

    def search_memory(self, keyword: str, limit: int = 5) -> List[Dict]:
        results = self.db.search_conversations_by_keyword(keyword, limit)
        logger.info(f"Memory search for '{keyword}' returned {len(results)} results")
        return results

    def parse_time_query(self, user_message: str) -> Optional[Dict[str, Any]]:
        message_lower = user_message.lower()
        now = datetime.now()

        if "last conversation" in message_lower or "most recent conversation" in message_lower:
            return {"query_type": "last_conversation"}

        days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
        for i, day in enumerate(days):
            if f"last {day}" in message_lower:
                days_back = (now.weekday() - i) % 7
                if days_back == 0:
                    days_back = 7
                target_date = now - timedelta(days=days_back)
                return {"query_type": "specific_date", "date": target_date}

        if "last night" in message_lower or "lastnight" in message_lower:
            target_date = now - timedelta(days=1)
            return {"query_type": "specific_date", "date": target_date}

        if "yesterday" in message_lower:
            target_date = now - timedelta(days=1)
            return {"query_type": "specific_date", "date": target_date}

        today_recall_phrases = ["earlier today", "what did we today", "what happened today",
                                "conversations today", "talked today", "discussed today"]
        if any(p in message_lower for p in today_recall_phrases):
            return {"query_type": "specific_date", "date": now}

        if "this morning" in message_lower:
            target_time = now.replace(hour=9, minute=0, second=0, microsecond=0)
            return {"query_type": "specific_time", "datetime": target_time}
        if "this afternoon" in message_lower:
            target_time = now.replace(hour=14, minute=0, second=0, microsecond=0)
            return {"query_type": "specific_time", "datetime": target_time}
        if "this evening" in message_lower:
            target_time = now.replace(hour=19, minute=0, second=0, microsecond=0)
            return {"query_type": "specific_time", "datetime": target_time}

        date_patterns = [
            r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2})',
            r'(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+(\d{1,2})',
            r'(\d{1,2})/(\d{1,2})'
        ]

        months = {
            'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
            'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12,
            'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'jun': 6, 'jul': 7, 'aug': 8,
            'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
        }

        for pattern in date_patterns[:2]:
            match = re.search(pattern, message_lower)
            if match:
                month_name = match.group(1)
                day = int(match.group(2))
                month = months.get(month_name)
                if month:
                    try:
                        target_date = datetime(now.year, month, day)
                        if target_date > now:
                            target_date = datetime(now.year - 1, month, day)
                        return {"query_type": "specific_date", "date": target_date}
                    except ValueError:
                        pass

        match = re.search(date_patterns[2], message_lower)
        if match:
            month = int(match.group(1))
            day = int(match.group(2))
            try:
                target_date = datetime(now.year, month, day)
                if target_date > now:
                    target_date = datetime(now.year - 1, month, day)
                return {"query_type": "specific_date", "date": target_date}
            except ValueError:
                pass

        time_patterns = [
            (r'(\d{1,2}):(\d{2})\s*(am|pm)', 'time_with_minutes_and_period'),
            (r'(\d{1,2})\s*(am|pm)', 'time_with_period_only'),
            (r'(\d{1,2}):(\d{2})', 'time_24h')
        ]

        for pattern, pattern_type in time_patterns:
            match = re.search(pattern, message_lower)
            if match:
                hour = int(match.group(1))
                minute = 0
                period = None

                if pattern_type == 'time_with_minutes_and_period':
                    minute = int(match.group(2))
                    period = match.group(3)
                elif pattern_type == 'time_with_period_only':
                    period = match.group(2)
                    minute = 0
                elif pattern_type == 'time_24h':
                    minute = int(match.group(2))

                if period:
                    if period == 'pm' and hour < 12:
                        hour += 12
                    elif period == 'am' and hour == 12:
                        hour = 0

                target_date = now
                if "last night" in message_lower or "lastnight" in message_lower:
                    target_date = now - timedelta(days=1)
                elif "yesterday" in message_lower:
                    target_date = now - timedelta(days=1)
                elif re.search(r'\btoday\b', message_lower) or "tonight" in message_lower:
                    target_date = now
                else:
                    for i, day in enumerate(days):
                        if f"last {day}" in message_lower:
                            days_back = (now.weekday() - i) % 7
                            if days_back == 0:
                                days_back = 7
                            target_date = now - timedelta(days=days_back)
                            break
                        elif f"{day}" in message_lower and "last" not in message_lower:
                            days_back = (now.weekday() - i) % 7
                            if days_back == 0:
                                target_date = now
                            else:
                                target_date = now - timedelta(days=days_back)
                            break

                target_datetime = target_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
                return {"query_type": "specific_time", "datetime": target_datetime}

        return None

    def recall_conversation_by_time(self, user_message: str) -> Optional[str]:
        time_info = self.parse_time_query(user_message)

        if not time_info:
            return None

        try:
            if time_info['query_type'] == 'last_conversation':
                conversation = self.db.get_last_conversation()
                if conversation:
                    return self._format_conversation_recall(conversation, "last conversation")
                else:
                    return "I couldn't find any previous conversations."

            elif time_info['query_type'] == 'specific_date':
                target_date = time_info['date']
                conversations = self.db.get_conversations_by_date(target_date)
                if conversations:
                    date_str = target_date.strftime('%A, %B %d, %Y')
                    return self._format_multiple_conversations(conversations, f"on {date_str}")
                else:
                    date_str = target_date.strftime('%A, %B %d, %Y')
                    return f"I couldn't find any conversations on {date_str}."

            elif time_info['query_type'] == 'specific_time':
                target_time = time_info['datetime']
                messages = self.db.get_messages_around_timestamp(target_time, window_minutes=30)
                if messages:
                    time_str = target_time.strftime('%B %d at %I:%M %p')
                    return self._format_time_based_messages(messages, f"around {time_str}")
                else:
                    time_str = target_time.strftime('%B %d at %I:%M %p')
                    return f"I couldn't find any messages around {time_str}."

        except Exception as e:
            logger.error(f"Error recalling conversation by time: {e}")
            return f"I encountered an error while searching: {str(e)}"

        return None

    def _format_conversation_recall(self, conversation: Dict, time_description: str) -> str:
        title = conversation.get('title', 'Untitled')
        created = conversation.get('created_at')
        messages = conversation.get('messages', [])

        if isinstance(created, str):
            created = datetime.fromisoformat(created)

        result = [f"Our {time_description} was titled '{title}' on {created.strftime('%A, %B %d at %I:%M %p')}:\n"]

        if messages:
            for msg in messages[:10]:
                role = "You" if msg['role'] == 'user' else "Me"
                content = msg['content'][:200] + "..." if len(msg['content']) > 200 else msg['content']
                result.append(f"{role}: {content}\n")
            if len(messages) > 10:
                result.append(f"\n... and {len(messages) - 10} more messages.")

        return "".join(result)

    def _format_multiple_conversations(self, conversations: List[Dict], time_description: str) -> str:
        result = [f"I found {len(conversations)} conversation(s) {time_description}:\n\n"]

        for i, conv in enumerate(conversations, 1):
            title = conv.get('title', 'Untitled')
            created = conv.get('created_at')
            message_count = conv.get('message_count', 0)

            if isinstance(created, str):
                created = datetime.fromisoformat(created)

            result.append(f"{i}. '{title}' at {created.strftime('%I:%M %p')} ({message_count} messages)\n")

            messages = conv.get('messages', [])
            if messages:
                for msg in messages[:2]:
                    role = "You" if msg['role'] == 'user' else "Me"
                    content = msg['content'][:150] + "..." if len(msg['content']) > 150 else msg['content']
                    result.append(f"   {role}: {content}\n")
            result.append("\n")

        return "".join(result)

    def _format_time_based_messages(self, messages: List[Dict], time_description: str) -> str:
        result = [f"Here's what we discussed {time_description}:\n\n"]

        current_conv = None
        for msg in messages:
            conv_title = msg.get('conversation_title', 'Untitled')

            if conv_title != current_conv:
                result.append(f"\n--- {conv_title} ---\n")
                current_conv = conv_title

            role = "You" if msg['role'] == 'user' else "Me"
            content = msg['content'][:200] + "..." if len(msg['content']) > 200 else msg['content']
            created = msg.get('created_at')

            if isinstance(created, str):
                created = datetime.fromisoformat(created)

            time_str = created.strftime('%I:%M %p')
            result.append(f"[{time_str}] {role}: {content}\n")

        return "".join(result)

    def chat(
        self,
        user_message: str,
        use_context: bool = True,
        context_length: int = 30,
        use_memory_search: bool = True,
        skip_introspection: bool = False,
        skip_actions: bool = False,
        skip_time_recall: bool = False
    ) -> str:
        """
        Main chat interface with semantic memory

        Args:
            user_message: The user's message
            use_context: Whether to include conversation history
            context_length: How many previous messages to include
            use_memory_search: Whether to search past conversations for relevant context
            skip_introspection: Skip introspection parser (used for document drops)
            skip_actions: Skip action executor (used for document drops)
            skip_time_recall: Skip time-based recall check (used for document drops)
        """
        # Check if this is a time-based recall query FIRST
        # Skipped for document drops to prevent the file content triggering false recall matches
        if not skip_time_recall:
            time_recall_result = None
            if self._has_recall_intent(user_message):
                time_recall_result = self.recall_conversation_by_time(user_message)
            if time_recall_result:
                if not self.current_conversation_id:
                    self.start_conversation()

                user_embedding = self.embedder.generate_embedding(user_message)
                message_id = self.db.add_message(
                    conversation_id=self.current_conversation_id,
                    role="user",
                    content=user_message
                )
                self.memory.add_message(
                    message_id=message_id,
                    conversation_id=self.current_conversation_id,
                    role="user",
                    content=user_message,
                    embedding=user_embedding,
                    timestamp=datetime.now()
                )

                assistant_embedding = self.embedder.generate_embedding(time_recall_result)
                assistant_message_id = self.db.add_message(
                    conversation_id=self.current_conversation_id,
                    role="assistant",
                    content=time_recall_result
                )
                self.memory.add_message(
                    message_id=assistant_message_id,
                    conversation_id=self.current_conversation_id,
                    role="assistant",
                    content=time_recall_result,
                    embedding=assistant_embedding,
                    timestamp=datetime.now()
                )

                logger.info(f"Time-based recall query processed: {user_message}")
                return time_recall_result

        # Ensure we have a conversation
        if not self.current_conversation_id:
            self.start_conversation()

        # Check for "forget/delete that" command
        forget_phrases = [
            "that's wrong", "that is wrong", "forget that", "delete that",
            "that is incorrect", "that's incorrect", "remove that",
            "that was wrong", "thats wrong", "thats incorrect"
        ]
        if any(phrase in user_message.lower().strip() for phrase in forget_phrases):
            try:
                recent = self.db.get_recent_messages(self.current_conversation_id, limit=5)
                last_assistant = next((m for m in reversed(recent) if m['role'] == 'assistant'), None)
                if last_assistant:
                    msg_id = str(last_assistant['id'])
                    try:
                        self.memory.collection.delete(ids=[msg_id])
                        logger.info(f"Deleted wrong response from ChromaDB: {msg_id}")
                        return "Got it — I've deleted that from my memory. What's the correct information?"
                    except Exception as de:
                        logger.warning(f"Could not delete from ChromaDB: {de}")
                        return "I tried to delete that but couldn't. Can you tell me the correct information?"
            except Exception as e:
                logger.warning(f"Forget command failed: {e}")

        # Generate embedding for user message
        user_embedding = self.embedder.generate_embedding(user_message)

        # Check for introspection commands FIRST (before action_executor)
        if self.introspection_parser and not skip_introspection:
            try:
                was_introspection, response = self.introspection_parser.parse_and_execute(user_message)
                if was_introspection and response:
                    message_id = self.db.add_message(
                        conversation_id=self.current_conversation_id,
                        role="user",
                        content=user_message
                    )
                    self.memory.add_message(
                        message_id=message_id,
                        conversation_id=self.current_conversation_id,
                        role="user",
                        content=user_message,
                        embedding=user_embedding,
                        timestamp=datetime.now()
                    )

                    assistant_embedding = self.embedder.generate_embedding(response)
                    assistant_message_id = self.db.add_message(
                        conversation_id=self.current_conversation_id,
                        role="assistant",
                        content=response
                    )
                    self.memory.add_message(
                        message_id=assistant_message_id,
                        conversation_id=self.current_conversation_id,
                        role="assistant",
                        content=response,
                        embedding=assistant_embedding,
                        timestamp=datetime.now()
                    )

                    logger.info(f"Introspection command processed: {user_message[:50]}")
                    return response
            except Exception as e:
                logger.error(f"Introspection error: {e}")

        # Check and execute action commands
        action_result = None if skip_actions else self.action_executor.process_command(user_message)

        if action_result and action_result['executed']:
            logger.info(f"Action: {action_result.get('action')} {action_result.get('target')}")
            action_type = action_result.get('action', 'action')
            target = action_result.get('target', 'target')
            if action_type == 'search':
                return f"Searching for: {target}"
            else:
                return f"Opening: {target}"

        # Save user message to database
        message_id = self.db.add_message(
            conversation_id=self.current_conversation_id,
            role="user",
            content=user_message
        )

        # Add to vector memory
        self.memory.add_message(
            message_id=message_id,
            conversation_id=self.current_conversation_id,
            role="user",
            content=user_message,
            embedding=user_embedding,
            timestamp=datetime.now()
        )

        # Build system prompt with memories
        if use_memory_search:
            system_prompt = self.build_system_prompt_with_memories(user_message)
        else:
            system_prompt = self.base_system_prompt

        # Build context
        conversation_history = []
        if use_context:
            conversation_history = self.get_conversation_context(context_length)

        # Skip Grok if AI is disabled
        if not self.ai_enabled:
            logger.info("AI disabled - skipping Grok call")
            return ""

        # Get response from Grok
        try:
            response = self.grok.chat_with_context(
                user_message=user_message,
                conversation_history=conversation_history[:-1],
                system_prompt=system_prompt
            )

            assistant_message = response["choices"][0]["message"]["content"]

            usage = response.get("usage", {})
            token_count = usage.get("total_tokens", 0)

            logger.info(f"Chat exchange completed. Tokens used: {token_count}")

            try:
                assistant_embedding = self.embedder.generate_embedding(assistant_message)
                assistant_message_id = self.db.add_message(
                    conversation_id=self.current_conversation_id,
                    role="assistant",
                    content=assistant_message,
                    token_count=token_count,
                    metadata={
                        "model": self.grok.model,
                        "usage": usage
                    }
                )
                self.memory.add_message(
                    message_id=assistant_message_id,
                    conversation_id=self.current_conversation_id,
                    role="assistant",
                    content=assistant_message,
                    embedding=assistant_embedding,
                    timestamp=datetime.now()
                )
            except Exception as e:
                logger.error(f"Failed to save assistant response: {e}")

            return assistant_message

        except Exception as e:
            error_str = str(e)
            if any(x in error_str.lower() for x in ["connection", "timeout", "network", "unreachable", "refused", "nodename", "failed to establish"]):
                logger.warning(f"Grok API unreachable: {e}")
                return "I'm currently offline. Local commands like PLC control still work."
            error_msg = f"Error during chat: {e}"
            logger.error(error_msg)
            self.db.log_system_event("ERROR", error_msg, {"conversation_id": self.current_conversation_id})
            raise

    def get_conversation_summary(self) -> Dict[str, Any]:
        if not self.current_conversation_id:
            return {"error": "No active conversation"}
        conversation = self.db.get_conversation(self.current_conversation_id)
        messages = self.db.get_conversation_messages(self.current_conversation_id)
        return {
            "id": conversation["id"],
            "title": conversation["title"],
            "message_count": conversation["message_count"],
            "created_at": conversation["created_at"],
            "updated_at": conversation["updated_at"],
            "messages": len(messages)
        }

    def list_recent_conversations(self, limit: int = 10) -> List[Dict]:
        return self.db.get_recent_conversations(limit)

    def get_memory_stats(self) -> Dict[str, Any]:
        return self.memory.get_stats()

    # ==========================================
    # VISION METHODS
    # ==========================================

    def select_monitor(self, monitor_number: Optional[int] = None):
        if hasattr(self, 'vision'):
            self.vision.select_monitor(monitor_number)
            return self.vision.get_selected_monitor_info()
        else:
            logger.warning("Vision system not initialized")
            return {"error": "Vision system not available"}

    def get_available_monitors(self) -> List[Dict]:
        if hasattr(self, 'vision'):
            return self.vision.get_monitors()
        else:
            return []

    def get_screen_vision(self, window_title: Optional[str] = None) -> str:
        if not hasattr(self, 'vision'):
            return "❌ Vision system not initialized. Install vision_integration.py"
        vision_data = self.vision.get_complete_vision(window_title)
        formatted_vision = self.vision.format_vision_for_agent(vision_data)
        logger.info("Screen vision acquired for agent")
        return formatted_vision

    def find_ui_element(self, name: str, control_type: Optional[str] = None) -> List[Dict]:
        if hasattr(self, 'vision'):
            return self.vision.find_elements(name=name, control_type=control_type)
        else:
            return []

    def get_vision_capabilities(self) -> str:
        if hasattr(self, 'vision'):
            return self.vision.get_capabilities_report()
        else:
            return "Vision system not initialized"

    # ==========================================
    # INTROSPECTION METHODS
    # ==========================================

    def list_my_modules(self) -> List[Dict[str, Any]]:
        if self.introspection:
            return self.introspection.list_modules()
        else:
            return []

    def read_my_code(self, filename: str) -> Optional[Dict[str, Any]]:
        if self.introspection:
            return self.introspection.read_source_file(filename)
        else:
            return None

    def get_my_module_info(self, filename: str) -> Optional[Dict[str, Any]]:
        if self.introspection:
            return self.introspection.get_module_info(filename)
        else:
            return None

    def find_my_function(self, function_name: str) -> List[Dict[str, Any]]:
        if self.introspection:
            return self.introspection.find_function(function_name)
        else:
            return []

    def find_my_class(self, class_name: str) -> List[Dict[str, Any]]:
        if self.introspection:
            return self.introspection.find_class(class_name)
        else:
            return []

    def search_my_code(self, keyword: str) -> List[Dict[str, Any]]:
        if self.introspection:
            return self.introspection.search_code(keyword)
        else:
            return []

    def get_my_system_overview(self) -> Dict[str, Any]:
        if self.introspection:
            return self.introspection.get_system_overview()
        else:
            return {"error": "Introspection not available"}

    def open_my_code_file(self, filename: str, editor: str = "notepad") -> Dict[str, Any]:
        if self.introspection:
            return self.introspection.open_file_in_editor(filename, editor)
        else:
            return {"error": "Introspection not available"}

    def open_my_folder(self) -> Dict[str, Any]:
        if self.introspection:
            return self.introspection.open_my_folder()
        else:
            return {"error": "Introspection not available"}

    def shutdown(self):
        logger.info(f"{self.name} shutting down")
        self.db.close()


def initialize_agent(grok_client, database, embedding_generator, memory_search, chore_db, plc_comm, agent_name: str = "GrokAgent", agent_root_path: str = None, introspection_parser=None) -> GrokAgent:
    try:
        agent = GrokAgent(grok_client, database, embedding_generator, memory_search, chore_db, plc_comm, agent_name, agent_root_path, introspection_parser)
        logger.info("Agent initialized successfully")
        return agent
    except Exception as e:
        logger.error(f"Failed to initialize agent: {e}")
        raise
