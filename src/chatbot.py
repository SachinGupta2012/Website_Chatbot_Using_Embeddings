from langchain.chains import ConversationalRetrievalChain
from langchain_groq import ChatGroq
from langchain.memory import ConversationBufferWindowMemory  # FIXED - use langchain.memory
from langchain_core.prompts import PromptTemplate
from langchain_community.vectorstores import FAISS

class WebsiteChatbot:
    def __init__(self, vector_store: FAISS, groq_api_key: str, 
                 model_name: str = "llama-3.3-70b-versatile", memory_window: int = 5):
        
        self.vector_store = vector_store
        self.memory = ConversationBufferWindowMemory(
            memory_key="chat_history",
            return_messages=True,
            k=memory_window,
            output_key="answer"
        )
        
        self.llm = ChatGroq(
            model=model_name,
            api_key=groq_api_key,
            temperature=0.1,
            max_tokens=1024
        )
        
        self.strict_prompt = """You are a strict question-answering assistant.
        
RULES:
1. Answer ONLY using the provided website context below.
2. If the answer is not in the context, respond EXACTLY with: "The answer is not available on the provided website."
3. No external knowledge. No apologies. No hallucinations.

Website Context:
{context}

Chat History:
{chat_history}

Question: {question}

Answer (strictly from context only):"""

        self.qa_prompt = PromptTemplate(
            input_variables=["context", "chat_history", "question"],
            template=self.strict_prompt
        )
        
        self.chain = ConversationalRetrievalChain.from_llm(
            llm=self.llm,
            retriever=self.vector_store.as_retriever(
                search_type="mmr",
                search_kwargs={"k": 6, "fetch_k": 10}
            ),
            memory=self.memory,
            combine_docs_chain_kwargs={"prompt": self.qa_prompt},
            return_source_documents=False
        )
    
    def ask(self, question: str) -> str:
        try:
            response = self.chain.invoke({"question": question})
            answer = response["answer"].strip()
            answer = answer.replace("<|eot_id|>", "").strip()
            
            uncertainty = ["i don't know", "i'm not sure", "cannot find", "not mentioned"]
            if any(marker in answer.lower() for marker in uncertainty):
                return "The answer is not available on the provided website."
            
            return answer if answer else "The answer is not available on the provided website."
        except Exception as e:
            return f"Error: {str(e)}"
    
    def clear_memory(self):
        self.memory.clear()