"""터미널에서 이미지 변환 함수를 바로 테스트하기 위한 스크립트.

사용법:
    python test_convert.py <입력파일> <목표포맷> [출력파일]

예시:
    python test_convert.py sample.png jpeg
    python test_convert.py sample.png webp output/sample.webp
"""

import sys

from converters.image_converter import convert_image


def main() -> None:
    if len(sys.argv) < 3:
        print("사용법: python test_convert.py <입력파일> <목표포맷> [출력파일]")
        sys.exit(1)

    input_path = sys.argv[1]
    output_format = sys.argv[2]
    output_path = sys.argv[3] if len(sys.argv) > 3 else None

    try:
        result_path = convert_image(input_path, output_format, output_path)
    except Exception as error:
        print(f"변환 실패: {error}")
        sys.exit(1)

    print(f"변환 완료: {result_path}")


if __name__ == "__main__":
    main()
