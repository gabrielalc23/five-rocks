from builders.faiss_adapter_builder import FaissAdapterBuilder
from decorators.injectable_decorator import injectable


@injectable
class ResumeDocumentsModule:
    def __init__(self, faiss_adapter_builder: FaissAdapterBuilder):
        self.faiss_adapter_builder: FaissAdapterBuilder = faiss_adapter_builder
        
    def start(self):
        print("ResumeDocumentsModule started!")
