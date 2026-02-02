def is_authorized(user: dict, document_meta: dict) -> bool:
    """
    Authorization predicate (FROZEN — Chat 02)

    A document is retrievable iff:
    - user.role ∈ document.allowed_roles
    - user.department == document.owner_department
    - user.clearance_level >= document.min_clearance_level
    """

    return (
        user["role"] in document_meta["allowed_roles"]
        and user["department"] == document_meta["owner_department"]
        and user["clearance_level"] >= document_meta["min_clearance_level"]
    )
