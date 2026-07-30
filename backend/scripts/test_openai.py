from langchain_openai import ChatOpenAI
from pydantic import SecretStr

from backend.config.settings import settings
from backend.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


def main() -> None:
    llm = ChatOpenAI(
        model=settings.llm_model,
        api_key=SecretStr(settings.openai_api_key),
        temperature=0,
    )

    response = llm.invoke("Say hello in one sentence.")

    logger.info("Response: %s", response.content)


if __name__ == "__main__":
    configure_logging()
    main()