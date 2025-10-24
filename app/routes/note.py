from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from app.schema.note import NoteCreate, Note, ContentCreate, Content
from app.schema.workspace import Collab
from database import notes, workspaces, contents
from bson import ObjectId
from auth import oauth2_scheme, verify_token  # Assuming you have these auth utilities

router = APIRouter('/note', tags=['notes'])

# OAuth dependency that will extract user info from token
async def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = verify_token(token)
    return payload  # Returns: user_id, workspace_id, access

@router.post('/create_note', response_model=Note)
async def create_note(note: NoteCreate, current_user: dict = Depends(get_current_user)):
    """
    Create a new note in the workspace
    Requires: 'rw' access
    """
    # Check if user has write access to the workspace
    if current_user['access'] not in ['rw']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Write access required to create notes"
        )
    
    # Verify that the workspace exists and user has access
    workspace = workspaces.find_one({
        'workspace_id': note.workspace_id,
        'user_id': current_user['user_id']  # or check in collabs collection
    })
    
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found or access denied"
        )
    
    note_data = note.model_dump()
    note_data['user_id'] = current_user['user_id']  # Ensure note is created by current user
    
    inserted_note = notes.insert_one(note_data)
    created_note = notes.find_one({'_id': inserted_note.inserted_id})
    created_note['note_id'] = str(created_note['_id'])
    del created_note['_id']
    
    return Note(**created_note)

@router.get('/notes', response_model=List[Note])
async def get_notes_of_workspace(
    workspace_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get all notes in a workspace
    Requires: 'r' or 'rw' access
    """
    if current_user['access'] not in ['r', 'rw']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Read access required to view notes"
        )
    
    # Verify workspace access
    workspace = workspaces.find_one({
        'workspace_id': workspace_id,
        'user_id': current_user['user_id']  # or check collabs
    })
    
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found or access denied"
        )
    
    notes_list = list(notes.find({'workspace_id': workspace_id}))
    
    for note in notes_list:
        note['note_id'] = str(note['_id'])
        del note['_id']
    
    return [Note(**note) for note in notes_list]

@router.get('/{note_id}', response_model=Note)
async def get_note(
    note_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get a specific note by ID
    Requires: 'r' or 'rw' access
    """
    if current_user['access'] not in ['r', 'rw']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Read access required to view note"
        )
    
    note = notes.find_one({'_id': ObjectId(note_id)})
    
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )
    
    # Verify user has access to the workspace containing this note
    workspace = workspaces.find_one({
        'workspace_id': note['workspace_id'],
        'user_id': current_user['user_id']  # or check collabs
    })
    
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this note"
        )
    
    note['note_id'] = str(note['_id'])
    del note['_id']
    
    return Note(**note)

@router.put('/{note_id}', response_model=Note)
async def update_note(
    note_id: str,
    note_update: dict,  # You might want to create an UpdateNote schema
    current_user: dict = Depends(get_current_user)
):
    """
    Update note header/metadata
    Requires: 'rw' access
    """
    if current_user['access'] not in ['rw']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Write access required to update notes"
        )
    
    note = notes.find_one({'_id': ObjectId(note_id)})
    
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )
    
    # Verify ownership or collaboration access
    if note['user_id'] != current_user['user_id']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only note owner can update note metadata"
        )
    
    # Remove None values from update
    update_data = {k: v for k, v in note_update.items() if v is not None}
    
    notes.update_one(
        {'_id': ObjectId(note_id)},
        {'$set': update_data}
    )
    
    updated_note = notes.find_one({'_id': ObjectId(note_id)})
    updated_note['note_id'] = str(updated_note['_id'])
    del updated_note['_id']
    
    return Note(**updated_note)

@router.delete('/{note_id}')
async def delete_note(
    note_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a note and all its contents
    Requires: 'rw' access and note ownership
    """
    if current_user['access'] not in ['rw']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Write access required to delete notes"
        )
    
    note = notes.find_one({'_id': ObjectId(note_id)})
    
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )
    
    # Only note owner can delete the note
    if note['user_id'] != current_user['user_id']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only note owner can delete the note"
        )
    
    # Delete the note and all its contents
    notes.delete_one({'_id': ObjectId(note_id)})
    contents.delete_many({'note_id': note_id})
    
    return {"message": "Note deleted successfully"}

@router.post('/{note_id}/content', response_model=Content)
async def add_content_to_note(
    note_id: str,
    content: ContentCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Add content to a note
    Requires: 'rw' access
    """
    if current_user['access'] not in ['rw']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Write access required to add content"
        )
    
    note = notes.find_one({'_id': ObjectId(note_id)})
    
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )
    
    # Verify user has access to modify this note
    workspace = workspaces.find_one({
        'workspace_id': note['workspace_id'],
        'user_id': current_user['user_id']  # or check collabs
    })
    
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this note"
        )
    
    content_data = content.model_dump()
    content_data['note_id'] = note_id
    
    inserted_content = contents.insert_one(content_data)
    created_content = contents.find_one({'_id': inserted_content.inserted_id})
    created_content['content_id'] = str(created_content['_id'])
    del created_content['_id']
    
    return Content(**created_content)

@router.get('/{note_id}/contents', response_model=List[Content])
async def get_note_contents(
    note_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get all contents of a note
    Requires: 'r' or 'rw' access
    """
    if current_user['access'] not in ['r', 'rw']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Read access required to view note contents"
        )
    
    note = notes.find_one({'_id': ObjectId(note_id)})
    
    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Note not found"
        )
    
    # Verify user has access to the workspace
    workspace = workspaces.find_one({
        'workspace_id': note['workspace_id'],
        'user_id': current_user['user_id']  # or check collabs
    })
    
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this note"
        )
    
    contents_list = list(contents.find({'note_id': note_id}).sort('section_no', 1))
    
    for content in contents_list:
        content['content_id'] = str(content['_id'])
        del content['_id']
    
    return [Content(**content) for content in contents_list]

@router.get('/user/notes', response_model=List[Note])
async def get_user_notes(current_user: dict = Depends(get_current_user)):
    """
    Get all notes created by the current user across all workspaces
    """
    user_notes = list(notes.find({'user_id': current_user['user_id']}))
    
    for note in user_notes:
        note['note_id'] = str(note['_id'])
        del note['_id']
    
    return [Note(**note) for note in user_notes]