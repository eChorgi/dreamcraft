from enum import StrEnum

class PromptKeys(StrEnum):
    IMAGINATE_ROLE = 'imaginate_role'
    FEASIBILITY_CHECK_ROLE = 'feasibility_check_role'
    IMAGINATE_QUERY = 'imaginate_query'
    FEASIBILITY_CHECK_QUERY = 'feasibility_check_query'
    IMAGINATE_QUERY_COPY = 'imaginate_query_copy'
    REACT = 'react'
