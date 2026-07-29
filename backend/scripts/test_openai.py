from pydantic import SecretStr
from langchain_openai import ChatOpenAI

from backend.config.settings import settings


def main() -> None:
    llm = ChatOpenAI(
        model=settings.llm_model,
        api_key=SecretStr(settings.openai_api_key),
        temperature=0,
    )

    response = llm.invoke("Say hello in one sentence.")

    print("\nResponse:")
    print(response.content)

if __name__ == "__main__":
    main()