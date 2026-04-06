import asyncio
import logging
from typing import Dict, Any, List, Optional
from dashboard.notify import send_message as send_telegram_message

logger = logging.getLogger(__name__)

class PolicyEngine:
    def __init__(self):
        self.registered_fetchers = {}
        self.registered_processors = {}
        self.registered_reactors = {}
        self._register_builtins()

    def _register_builtins(self):
        # Sample fetchers
        self.register_fetcher("gmail", self.fetch_gmail)
        self.register_fetcher("mock", self.fetch_mock)

        # Sample processors
        self.register_processor("summarize", self.process_summarize)
        self.register_processor("identity", self.process_identity)

        # Sample reactors
        self.register_reactor("slack", self.react_slack)
        self.register_reactor("telegram", self.react_telegram)
        self.register_reactor("mock", self.react_mock)

    def register_fetcher(self, name: str, func: callable):
        self.registered_fetchers[name] = func

    def register_processor(self, name: str, func: callable):
        self.registered_processors[name] = func

    def register_reactor(self, name: str, func: callable):
        self.registered_reactors[name] = func

    async def execute_workflow(self, workflow_name: str, params: Dict[str, Any]):
        """
        Executes a workflow: Fetch -> Process -> React
        Params should contain:
            fetcher: str
            fetch_params: dict
            processor: str
            process_params: dict
            reactor: str
            react_params: dict
        """
        logger.info(f"Executing workflow: {workflow_name}")
        
        # 1. Fetch
        fetcher_name = params.get("fetcher", "mock")
        fetch_params = params.get("fetch_params", {})
        fetch_func = self.registered_fetchers.get(fetcher_name)
        if not fetch_func:
            logger.error(f"Fetcher {fetcher_name} not found")
            return
        
        data = await fetch_func(fetch_params)
        logger.info(f"Fetched data: {data}")

        # 2. Process
        processor_name = params.get("processor", "identity")
        process_params = params.get("process_params", {})
        process_func = self.registered_processors.get(processor_name)
        if not process_func:
            logger.error(f"Processor {processor_name} not found")
            return
        
        processed_data = await process_func(data, process_params)
        logger.info(f"Processed data: {processed_data}")

        # 3. React
        reactor_name = params.get("reactor", "mock")
        react_params = params.get("react_params", {})
        reactor_func = self.registered_reactors.get(reactor_name)
        if not reactor_func:
            logger.error(f"Reactor {reactor_name} not found")
            return
        
        await reactor_func(processed_data, react_params)
        logger.info(f"Reaction completed")

    # --- Built-in Implementations ---

    async def fetch_gmail(self, params: Dict[str, Any]):
        # Mocking Gmail fetch
        return "New email from: support@example.com - Subject: Issue Report"

    async def fetch_mock(self, params: Dict[str, Any]):
        return params.get("mock_data", "Mock Data")

    async def process_summarize(self, data: Any, params: Dict[str, Any]):
        # Mocking summarization
        return f"Summary: {data[:20]}..."

    async def process_identity(self, data: Any, params: Dict[str, Any]):
        return data

    async def react_slack(self, data: Any, params: Dict[str, Any]):
        # Mocking Slack post
        logger.info(f"POSTing to Slack: {data}")

    async def react_telegram(self, data: Any, params: Dict[str, Any]):
        # Actual Telegram notification if configured
        await send_telegram_message(str(data))

    async def react_mock(self, data: Any, params: Dict[str, Any]):
        logger.info(f"Mock reaction with data: {data}")

policy_engine = PolicyEngine()
