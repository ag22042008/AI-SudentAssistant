from langchain_community.document_loaders import PyPDFLoader,WebBaseLoader,csv_loader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_mistralai import MistralAIEmbeddings
from langchain_community.vectorstores import Chroma 
from dotenv import load_dotenv
load_dotenv()
links=["https://en.wikipedia.org/wiki/Cloud_computing",
       "https://www.shapeblue.com/acs-beginners-part-1-introduction/"]
data4=WebBaseLoader(links)
docs4=data4.load()

data = PyPDFLoader(r"C:\Users\coone\OneDrive\Desktop\Rag_project\document loaders\deeplearning.pdf")
docs = data.load()
splitter = RecursiveCharacterTextSplitter(
    chunk_size = 1000,
    chunk_overlap = 200
)

chunks = splitter.split_documents(docs)
chunks2=splitter.split_documents(docs4)

embedding_model = MistralAIEmbeddings()

vectorstore = Chroma.from_documents(
    documents= chunks+chunks2,
    embedding=embedding_model,
    persist_directory="chroma_db"
)