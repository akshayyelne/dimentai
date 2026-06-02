from google.cloud import firestore
from google.cloud import discoveryengine_v1beta as discoveryengine
from datetime import datetime

def sanitize_data(data):
    """
    Recursively converts complex types. 
    Converts timestamps into Unix millisecond integers to match the Data Store number schema.
    """
    if isinstance(data, dict):
        return {k: sanitize_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_data(item) for item in data]
    elif isinstance(data, datetime) or hasattr(data, 'timestamp'):
        return int(data.timestamp() * 1000)
    else:
        return data

def sync_firestore_to_vertex_search():
    print("Initializing clients...")
    db = firestore.Client(project="dimentai1", database="dimentdata")
    docs = db.collection("patients").stream()
    
    search_client = discoveryengine.DocumentServiceClient()
    parent = "projects/dimentai1/locations/global/collections/default_collection/dataStores/dimentdata-search_1779850025667/branches/default_branch"
    print(f"Targeting Data Store Path: {parent}\n")
    
    # ---- SIT CLEAN PURGE BLOCK START ----
    print("Wiping old data store documents to ensure clean SIT data isolation...")
    try:
        list_req = discoveryengine.ListDocumentsRequest(parent=parent)
        docs_to_delete = search_client.list_documents(request=list_req)
        
        deleted_count = 0
        for d in docs_to_delete:
            search_client.delete_document(name=d.name)
            deleted_count += 1
        print(f"✨ Successfully purged {deleted_count} old index documents.\n")
    except Exception as purge_err:
        print(f"Note: Safe purge skipped or empty: {purge_err}\n")
    # ---- SIT CLEAN PURGE BLOCK END ----

    count = 0
    for doc in docs:
        clean_patient_data = sanitize_data(doc.to_dict())
        print(f"Syncing patient profile: {doc.id}")
        
        document = discoveryengine.Document(id=doc.id, struct_data=clean_patient_data)
        request = discoveryengine.CreateDocumentRequest(parent=parent, document=document, document_id=doc.id)
        
        try:
            search_client.create_document(request=request)
            count += 1
            print(f" -> Successfully indexed: {doc.id}")
        except Exception as e:
            if "AlreadyExists" in str(type(e)) or "409" in str(e):
                try:
                    # Construct the fully qualified document resource name for the update path
                    document.name = f"{parent}/documents/{doc.id}"
                    update_request = discoveryengine.UpdateDocumentRequest(document=document)
                    search_client.update_document(request=update_request)
                    count += 1
                    print(f" -> Updated existing profile: {doc.id}")
                except Exception as update_err:
                    print(f"Failed to update document {doc.id}: {update_err}")
            else:
                print(f"Failed to ingest document {doc.id}: {e}")
                
    print(f"\n🚀 Successfully indexed {count} patient profiles directly!")

if __name__ == "__main__":
    sync_firestore_to_vertex_search()