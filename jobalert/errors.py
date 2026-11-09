"""바깥(사이트, Discord)과 주고받다 생긴 오류

오류 메시지에는 요청 주소를 넣지 않는다. 주소 안에 API 키나 웹훅 토큰이 들어 있기 때문.
"""


class SourceError(Exception):
    """출처에서 공고를 가져오지 못함"""


class SendError(Exception):
    """Discord 로 보내지 못함"""
