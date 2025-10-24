from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from app.schema.workspace import WorkspaceCreate, Workspace, CollabCreate, Collab
from database import workspaces, collabs, notes, contents
from bson import ObjectId
from auth import oauth2_scheme, verify_token
from datetime import datetime

router = APIRouter('/workspace', tags=['workspaces'])

# OAuth dependency that will extract user info from token
async def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = verify_token(token)
    return payload  # Returns: user_id, workspace_id, access

@router.post('/create', response_model=Workspace)
async def create_workspace(workspace: WorkspaceCreate, current_user: dict = Depends(get_current_user)):
 
    workspace_data = workspace.model_dump()
    workspace_data['user_id'] = current_user['user_id']
    workspace_data['created_at'] = datetime.now()
    inserted_workspace = workspaces.insert_one(workspace_data)
    created_workspace = workspaces.find_one({'_id': inserted_workspace.inserted_id})
    
 
    collab_data = {
        'workspace_id': str(inserted_workspace.inserted_id),
        'user_id': current_user['user_id'],
        'access': 'rw',
    }
    collabs.insert_one(collab_data)
    
    created_workspace['workspace_id'] = str(created_workspace['_id'])
    del created_workspace['_id']
    
    return Workspace(**created_workspace)

@router.get('/list', response_model=List[Workspace])
async def get_user_workspaces(current_user: dict = Depends(get_current_user)):

    user_collabs = list(collabs.find({'user_id': current_user['user_id']}))
    workspace_ids = [collab['workspace_id'] for collab in user_collabs]
    
    workspaces_list = list(workspaces.find({'_id': {'$in': [ObjectId(wid) for wid in workspace_ids]}}))
    
    for workspace in workspaces_list:
        workspace['workspace_id'] = str(workspace['_id'])
        del workspace['_id']
        
        # Add user's access level to workspace response
        user_collab = next((collab for collab in user_collabs if collab['workspace_id'] == workspace['workspace_id']), None)
        if user_collab:
            workspace['user_access'] = user_collab['access']
    
    return [Workspace(**workspace) for workspace in workspaces_list]

@router.get('/{workspace_id}', response_model=Workspace)
async def get_workspace(
    workspace_id: str,
    current_user: dict = Depends(get_current_user)
):
    
    user_collab = collabs.find_one({
        'workspace_id': workspace_id,
        'user_id': current_user['user_id']
    })
    
    if not user_collab:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this workspace"
        )
    
    workspace = workspaces.find_one({'_id': ObjectId(workspace_id)})
    
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found"
        )
    
    workspace['workspace_id'] = str(workspace['_id'])
    workspace['user_access'] = user_collab['access']
    del workspace['_id']
    
    return Workspace(**workspace)

@router.put('/{workspace_id}', response_model=Workspace)
async def update_workspace(
    workspace_id: str,
    workspace_update: dict,
    current_user: dict = Depends(get_current_user)
):
    """
    Update workspace metadata
    Requires: 'rw' access and ownership
    """
    # Verify user has write access and is owner
    workspace = workspaces.find_one({'_id': ObjectId(workspace_id)})
    
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found"
        )
    
    # Check if user is the owner
    if workspace['user_id'] != current_user['user_id']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only workspace owner can update workspace metadata"
        )
    
    # Remove None values from update
    update_data = {k: v for k, v in workspace_update.items() if v is not None}
    
    workspaces.update_one(
        {'_id': ObjectId(workspace_id)},
        {'$set': update_data}
    )
    
    updated_workspace = workspaces.find_one({'_id': ObjectId(workspace_id)})
    updated_workspace['workspace_id'] = str(updated_workspace['_id'])
    updated_workspace['user_access'] = 'rw'  # Owner always has rw access
    del updated_workspace['_id']
    
    return Workspace(**updated_workspace)

@router.delete('/{workspace_id}')
async def delete_workspace(
    workspace_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Delete a workspace and all its notes and contents
    Requires: 'rw' access and ownership
    """
    workspace = workspaces.find_one({'_id': ObjectId(workspace_id)})
    
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found"
        )
    
    # Check if user is the owner
    if workspace['user_id'] != current_user['user_id']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only workspace owner can delete the workspace"
        )
    
    # Delete workspace, collabs, notes, and contents
    workspaces.delete_one({'_id': ObjectId(workspace_id)})
    collabs.delete_many({'workspace_id': workspace_id})
    
    # Get all notes in this workspace and delete them along with their contents
    workspace_notes = list(notes.find({'workspace_id': workspace_id}))
    for note in workspace_notes:
        note_id = str(note['_id'])
        contents.delete_many({'note_id': note_id})
    
    notes.delete_many({'workspace_id': workspace_id})
    
    return {"message": "Workspace and all associated data deleted successfully"}

@router.post('/{workspace_id}/collaborators', response_model=Collab)
async def add_collaborator(
    workspace_id: str,
    collab: CollabCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Add a collaborator to workspace
    Requires: 'rw' access and ownership
    """
    workspace = workspaces.find_one({'_id': ObjectId(workspace_id)})
    
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found"
        )
    
    # Check if user is the owner
    if workspace['user_id'] != current_user['user_id']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only workspace owner can add collaborators"
        )
    
    # Check if user is already a collaborator
    existing_collab = collabs.find_one({
        'workspace_id': workspace_id,
        'user_id': collab.user_id
    })
    
    if existing_collab:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already a collaborator in this workspace"
        )
    
    collab_data = collab.model_dump()
    collab_data['workspace_id'] = workspace_id
    
    inserted_collab = collabs.insert_one(collab_data)
    created_collab = collabs.find_one({'_id': inserted_collab.inserted_id})
    created_collab['collab_id'] = str(created_collab['_id'])
    del created_collab['_id']
    
    return Collab(**created_collab)

@router.get('/{workspace_id}/collaborators', response_model=List[Collab])
async def get_workspace_collaborators(
    workspace_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Get all collaborators of a workspace
    Requires: 'r' or 'rw' access to the workspace
    """
    # Verify user has access to this workspace
    user_collab = collabs.find_one({
        'workspace_id': workspace_id,
        'user_id': current_user['user_id']
    })
    
    if not user_collab:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this workspace"
        )
    
    collaborators = list(collabs.find({'workspace_id': workspace_id}))
    
    for collab in collaborators:
        collab['collab_id'] = str(collab['_id'])
        del collab['_id']
    
    return [Collab(**collab) for collab in collaborators]

@router.put('/{workspace_id}/collaborators/{user_id}')
async def update_collaborator_access(
    workspace_id: str,
    user_id: str,
    access_update: dict,
    current_user: dict = Depends(get_current_user)
):
    """
    Update collaborator access level
    Requires: 'rw' access and ownership
    """
    workspace = workspaces.find_one({'_id': ObjectId(workspace_id)})
    
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found"
        )
    
    # Check if user is the owner
    if workspace['user_id'] != current_user['user_id']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only workspace owner can update collaborator access"
        )
    
    # Prevent owner from changing their own access
    if user_id == current_user['user_id']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change owner's access level"
        )
    
    collab = collabs.find_one({
        'workspace_id': workspace_id,
        'user_id': user_id
    })
    
    if not collab:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collaborator not found"
        )
    
    collabs.update_one(
        {'_id': collab['_id']},
        {'$set': {'access': access_update.get('access')}}
    )
    
    return {"message": "Collaborator access updated successfully"}

@router.delete('/{workspace_id}/collaborators/{user_id}')
async def remove_collaborator(
    workspace_id: str,
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    """
    Remove a collaborator from workspace
    Requires: 'rw' access and ownership
    """
    workspace = workspaces.find_one({'_id': ObjectId(workspace_id)})
    
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found"
        )
    
    # Check if user is the owner
    if workspace['user_id'] != current_user['user_id']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only workspace owner can remove collaborators"
        )
    
    # Prevent owner from removing themselves
    if user_id == current_user['user_id']:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove owner from workspace"
        )
    
    collab = collabs.find_one({
        'workspace_id': workspace_id,
        'user_id': user_id
    })
    
    if not collab:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Collaborator not found"
        )
    
    collabs.delete_one({'_id': collab['_id']})
    
    return {"message": "Collaborator removed successfully"}

@router.get('/user/owned', response_model=List[Workspace])
async def get_user_owned_workspaces(current_user: dict = Depends(get_current_user)):
    """
    Get all workspaces owned by the current user
    """
    owned_workspaces = list(workspaces.find({'user_id': current_user['user_id']}))
    
    for workspace in owned_workspaces:
        workspace['workspace_id'] = str(workspace['_id'])
        workspace['user_access'] = 'rw'  # Owner always has rw access
        del workspace['_id']
    
    return [Workspace(**workspace) for workspace in owned_workspaces]