from app.models.groups import Group, GroupMember
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.company import CompanyMember
from app.models.documents import Document, DocumentPermission
from fastapi import HTTPException
from app.models.user import User
class GroupService:
    def __init__(
        self,
        db: AsyncSession,
    ):
        self.db = db

    async def create_group(
        self,
        company_id,
        group_name,
        created_by
    ):  
        try:
            stmt = (
                select(Group)
                .where(Group.company_id == company_id)
                .where(Group.name == group_name)
            )

            result = await self.db.execute(stmt)
            existing_group = result.scalars().first()
            if existing_group:
                raise HTTPException(status_code=400, detail="Group already exists")

            group = Group(
            company_id=company_id,
            name=group_name,
            is_default=False,
            created_by=created_by,
            updated_by=created_by
            )
            self.db.add(group)
            await self.db.commit()
            await self.db.refresh(group)
            return group
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=str(e))
    
    async def get_groups(
        self,
        company_id
    ):
        try:
            stmt = (
                select(Group)
                .where(Group.company_id == company_id)
            )
            result = await self.db.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=str(e))

    async def update_group(self, company_id, group_id, group_name, is_default, updated_by):
        try:
            stmt = (
                select(Group)
                .where(Group.company_id == company_id)
                .where(Group.id == group_id)
            )
            result = await self.db.execute(stmt)
            group = result.scalars().first()
            if not group:
                raise HTTPException(status_code=404, detail="Group not found")
            if group.created_by != updated_by:
                raise HTTPException(status_code=403, detail=f"You are not authorized to update this group.")
            
            group.name = group_name
            group.is_default = is_default
            group.updated_by = updated_by
            await self.db.commit()
            await self.db.refresh(group)
            return group
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=str(e))
    
    async def delete_group(self, company_id, group_id, updated_by):
        try:
            stmt = (
                select(Group)
                .where(Group.company_id == company_id)
                .where(Group.id == group_id)
            )
            result = await self.db.execute(stmt)
            group = result.scalars().first()
            if not group:
                raise HTTPException(status_code=404, detail="Group not found")
            if group.created_by != updated_by:
                raise HTTPException(status_code=403, detail=f"You are not authorized to update this group.")
            
            await self.db.delete(group)
            await self.db.commit()
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=str(e))
    
    async def add_group_members(
        self,
        company_id,
        group_id,
        group_members,
        updated_by
    ):
        try:
            stmt = (
                select(Group)
                .where(Group.id == group_id)
                .where(Group.company_id == company_id)
            )

            result = await self.db.execute(stmt)
            group = result.scalar_one_or_none()

            if not group:
                raise HTTPException(
                    status_code=404,
                    detail="Group not found"
                )

            if group.created_by != updated_by:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to update this group."
                )

            stmt = (
                select(CompanyMember.user_id)
                .where(
                    CompanyMember.company_id == company_id,
                    CompanyMember.user_id.in_(group_members),
                    CompanyMember.status == "active"
                )
            )

            result = await self.db.execute(stmt)

            valid_member_ids = set(result.scalars().all())

            invalid_member_ids = set(group_members) - valid_member_ids

            if invalid_member_ids:
                raise HTTPException(
                    status_code=400,
                    detail="One or more users are not active members of this company."
                )

            for user_id in valid_member_ids:
                group_member = GroupMember(
                    group_id=group_id,
                    user_id=user_id,
                )

                self.db.add(group_member)

            await self.db.commit()

            return group

        except HTTPException:
            await self.db.rollback()
            raise

        except Exception as e:
            await self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail=str(e)
            )

    async def remove_group_member(self, company_id, group_id, user_id, updated_by):
        try:
            stmt = (
                select(Group)
                .where(Group.id == group_id)
                .where(Group.company_id == company_id)
            )

            result = await self.db.execute(stmt)
            group = result.scalar_one_or_none()

            if not group:
                raise HTTPException(
                    status_code=404,
                    detail="Group not found"
                )

            # if group.created_by != updated_by:
            #     raise HTTPException(
            #         status_code=403,
            #         detail="You are not authorized to update this group."
            #     )

            stmt = (
                select(GroupMember)
                .where(GroupMember.group_id == group_id)
                .where(GroupMember.user_id == user_id)
            )

            result = await self.db.execute(stmt)
            group_member = result.scalar_one_or_none()

            if not group_member:
                raise HTTPException(
                    status_code=404,
                    detail="Group member not found"
                )

            await self.db.delete(group_member)
            await self.db.commit()

            return group

        except HTTPException:
            await self.db.rollback()
            raise

        except Exception as e:
            await self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail=str(e)
            )
    
    async def update_group_permissions(self, company_id, group_id, document_ids, updated_by):
        try:
            stmt = (
                select(Group)
                .where(Group.id == group_id)
                .where(Group.company_id == company_id)
            )

            result = await self.db.execute(stmt)
            group = result.scalar_one_or_none()

            if not group:
                raise HTTPException(
                    status_code=404,
                    detail="Group not found"
                )

            if group.created_by != updated_by:
                raise HTTPException(
                    status_code=403,
                    detail="You are not authorized to update this group."
                )

            # Tenant isolation: every document being granted must actually belong to
            # this company, not just exist somewhere in the documents table.
            stmt = (
                select(Document.id, Document.visibility)
                .where(
                    Document.company_id == company_id,
                    Document.id.in_(document_ids),
                )
            )
            result = await self.db.execute(stmt)
            found = result.all()

            valid_document_ids = {row.id for row in found}
            invalid_document_ids = set(document_ids) - valid_document_ids
            if invalid_document_ids:
                raise HTTPException(
                    status_code=400,
                    detail="One or more documents do not belong to this company."
                )

            # A group grant only means something once the document is no longer
            # company-wide (a company_wide doc bypasses permission rows entirely at
            # retrieval time) — require that switch to have already happened via the
            # document endpoint, rather than silently flipping it from here.
            still_company_wide = {row.id for row in found if row.visibility == "company_wide"}
            if still_company_wide:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        "One or more documents are still 'company_wide'. "
                        "Restrict them via PATCH /api/documents/{id}/permissions first."
                    )
                )

            # user_id.is_(None) scopes this to group-level grants only, so a direct
            # per-user share on one of these documents is never touched by this call.
            stmt = (
                select(DocumentPermission.document_id)
                .where(
                    DocumentPermission.group_id == group_id,
                    DocumentPermission.user_id.is_(None),
                )
            )
            result = await self.db.execute(stmt)
            existing_document_ids = set(result.scalars().all())

            if existing_document_ids == valid_document_ids:
                return group

            additions = valid_document_ids - existing_document_ids
            deletions = existing_document_ids - valid_document_ids

            for document_id in additions:
                self.db.add(DocumentPermission(
                    document_id=document_id,
                    group_id=group_id,
                    company_id=company_id,
                ))

            if deletions:
                stmt = (
                    select(DocumentPermission)
                    .where(
                        DocumentPermission.group_id == group_id,
                        DocumentPermission.user_id.is_(None),
                        DocumentPermission.document_id.in_(deletions),
                    )
                )
                result = await self.db.execute(stmt)
                for row in result.scalars().all():
                    await self.db.delete(row)

            await self.db.commit()

            return group

        except HTTPException:
            await self.db.rollback()
            raise

        except Exception as e:
            await self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail=str(e)
            )

    async def get_group_members(self, company_id, group_id):
        try:
            stmt = (
                select(User)
                .join(CompanyMember, User.id == CompanyMember.user_id)
                .join(GroupMember, User.id == GroupMember.user_id)
                .where(
                    GroupMember.group_id == group_id,
                    CompanyMember.company_id == company_id,
                )
            )

            result = await self.db.execute(stmt)
            return result.scalars().all()
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(
                status_code=500,
                detail=str(e)
            )