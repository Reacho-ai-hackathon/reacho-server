from ast import Call
import threading
import asyncio
import logging
import aiofiles
from datetime import datetime

from bson import ObjectId

from storage.db_utils import CRUDBase
from storage.models.call_metadata import CallMetadata
from storage.models.campaign import Campaign
from storage.models.user import User, UserCreate, UserUpdate
from .voice_call_service import VoiceCallService
from .speech_recognition_service import SpeechRecognitionService
from .ai_response_handler import AIResponseHandler
from .text_to_speech_service import TextToSpeechService
from .data_logging_service import DataLoggingService
from .utils import analyze_overall_sentiment, safe_log_doc
from storage.models import User, UserCreate, UserUpdate, Campaign, CampaignCreate, CampaignUpdate, Call, CallCreate, CallUpdate, CallMetadata, CallMetadataCreate, CallMetadataUpdate

# Configure module logger
logger = logging.getLogger(__name__)



# Initialising core DB components
class UserCRUD(CRUDBase[User]):
    def __init__(self):
        super().__init__(User, "users")

    async def find_by_phone(self, phno: str):
        """Find a user by phone number."""
        return await self.find_one({"phno": phno})

class CampaignCRUD(CRUDBase[Campaign]):
    def __init__(self):
        super().__init__(Campaign, "campaigns")

class CallCRUD(CRUDBase[Call]):
    def __init__(self):
        super().__init__(Call, "calls")


class CallMetadataCRUD(CRUDBase[CallMetadata]):
    def __init__(self):
        super().__init__(CallMetadata, "call_metadata")

    async def append_chunk(self, call_id, chunk):
        collection = await self.get_collection()
        await collection.update_one(
            {"call_id": call_id},
            {"$push": {"chunks": chunk.dict()}}
        )

class CallOrchestrator:
    """Manages the state of each call and coordinates the flow between services"""
    def __init__(self, call_queue_ref, call_states_ref, active_connections_ref):
        logger.info("Initializing CallOrchestrator")
        self.call_queue = call_queue_ref
        self.call_states = call_states_ref
        self.active_connections = active_connections_ref
        self.voice_service = VoiceCallService()
        self.speech_service = SpeechRecognitionService()
        self.ai_handler = AIResponseHandler()
        self.tts_service = TextToSpeechService()
        self.data_logger = DataLoggingService()
        self._processing_task = None
        self.user_crud = UserCRUD()
        self.campaign_crud = CampaignCRUD()
        self.call_crud = CallCRUD()
        self.call_metadata_crud = CallMetadataCRUD()
        # NOTE: Ensure MongoDB client/collections are used within the same event loop as FastAPI/Uvicorn
        logger.info("CallOrchestrator initialized successfully")

    async def process_csv(self, csv_file_path, campaign_id, campaign):
        import csv
        logger.info(f"Processing CSV file: {csv_file_path}")
        try:
            with open(csv_file_path, 'r') as file:
                csv_reader = csv.DictReader(file)
                count = 0
                for row in csv_reader:
                    if 'phno' not in row:
                        logger.warning(f"Skipping row without phno: {row}")
                        continue

                    user_data = UserCreate(
                        name=row["name"],
                        age=row["age"],
                        gender=row["gender"],
                        phno=row["phno"],
                        email=row["email"],
                        organisation=row["organisation"],
                        designation=row["designation"],
                    )
                    # Check if user with this phone number exists
                    existing_user = await self.user_crud.find_by_phone(row["phno"])
                    if existing_user:
                        logger.info(f"User with phno {row['phno']} exists. Updating user.")
                        # Use UserUpdate model for updating user details
                        update_data = UserUpdate(**user_data.model_dump())
                        user = await self.user_crud.update(str(existing_user.id), update_data)
                        logger.info(f"Updated user: {user}")
                    else:
                        logger.info(f"Creating user: {user_data}")
                        user = await self.user_crud.create(user_data)
                        logger.info(f"Created user: {user}")
                    
                    logger.debug(f"Queueing call to: {row['phno']}")
                    self.call_queue.put({**row, "campaign_id":campaign_id, "user_id":str(user.id), "campaign": campaign})
                    logger.debug(f"Total row info: {row['name']}")
                    count += 1
            logger.info(f"Successfully processed CSV and queued {count} calls")
            return {"status": "success", "message": f"Processed CSV and queued {count} calls"}
        except Exception as e:
            logger.error(f"Error processing CSV file: {e}", exc_info=True)
            await self.data_logger.log_error('csv_processing', str(e), {'file_path': csv_file_path})
            return {"status": "error", "message": str(e)}

    async def start_call_processing(self):
        logger.info("Starting call processing as an async background task in the main event loop")
        # Use asyncio.create_task to ensure the task runs in the current event loop
        asyncio.create_task(self._process_call_queue())

    async def _process_call_queue(self):
        logger.info("Call queue processing loop started")
        queue_empty_count = 0
        while True:
            if not self.call_queue.empty():
                queue_empty_count = 0  # Reset counter when there are calls
                queue_size = self.call_queue.qsize()
                logger.info(f"Processing next call from queue (remaining: {queue_size})")
                lead_info = self.call_queue.get()
                logger.info(f"Initiating call to: {lead_info.get('phno')}")
                try:
                    call_sid = await self.voice_service.make_call(lead_info)
                    logger.info(f"Call initiated successfully with SID: {call_sid}")
                    # Store call_sid in lead_info for reference in other methods
                    lead_info['call_sid'] = call_sid
                    self.call_states[call_sid] = {
                        'lead_info': lead_info,
                        'transcript': '',
                        'responses': [],
                        'status': 'initiated',
                        'start_time': datetime.now().isoformat()
                    }
                    logger.info(f"Call state initialized for SID: {call_sid}")
                    await self.data_logger.log_call_event(call_sid, 'initiated', lead_info)
                except Exception as e:
                    logger.error(f"Error initiating call: {e}", exc_info=True)
                    await self.data_logger.log_error('call_initiation', str(e), lead_info)
                logger.info("Waiting 5 seconds before processing next call")
                await asyncio.sleep(5)
            else:
                logger.debug("Call queue empty, waiting 10 seconds")
                queue_empty_count += 1
                if queue_empty_count >= 10:  # Use >= for safety
                    logger.info("No calls in queue for 10 checks, exiting loop")
                    break
                await asyncio.sleep(10)

    async def handle_call_status_update(self, call_sid, status):
        logger.info(f"Call status update for SID {call_sid}: {status}")
        call_obj = await self.call_crud.find_one({"call_sid": call_sid})
        if call_obj:
            logger.info(f"Updating call record in DB for SID {call_sid} to status {status}")


            # Set call_end_time if status is terminal
            terminal_statuses = ['completed', 'failed', 'busy', 'no-answer', 'canceled']
            update_kwargs = {"status": status}
            if status in terminal_statuses:
                update_kwargs["call_end_time"] = datetime.now()
            
            if status == 'completed':
                logger.info(f"Updating call record in DB with sentiment generation {update_kwargs}")
                call_metadata = await self.call_metadata_crud.find_one({"call_id": ObjectId(call_obj.id)});
                logger.info(f"CAll meta data {call_metadata}")
                chunks = call_metadata.chunks
                logger.info(f"Updating call record with chunks {chunks}")
                 # Convert CallChunk objects to dicts before sentiment analysis
                chunk_dicts = [chunk.model_dump() for chunk in chunks]
                logger.info(f"Updating call record with chunk dicts {chunk_dicts}")
                sentiment = analyze_overall_sentiment(chunk_dicts);
                update_kwargs["sentiment"] = sentiment;
                logger.info(f"Updating call record in DB for SID {call_sid} to sentiment {sentiment}")

            update_data = CallUpdate(**update_kwargs)
            await self.call_crud.update(str(call_obj.id), update_data)
            await self.data_logger.log_call_event(call_sid, status)

            # # Optionally update in-memory state if you want to keep it in sync
            # if call_sid in self.call_states:
            #     self.call_states[call_sid]['status'] = status
            #     if status in ['completed', 'failed', 'busy', 'no-answer', 'canceled']:
            #         logger.info(f"Call {call_sid} ended with status: {status}")
            #         if call_sid in self.active_connections:
            #             logger.info(f"Removing active connection for call {call_sid}")
            #             del self.active_connections[call_sid]
            #         self.call_states[call_sid]['end_time'] = datetime.now().isoformat()
            #         logger.info(f"Logging call completion for {call_sid}")
            #         await self.data_logger.log_call_completion(call_sid, self.call_states[call_sid])
        else:
            logger.warning(f"No call record found in DB for call SID: {call_sid}")
        return {"status": "success"}

