from rembg import remove


def remove_background(input_path: str, output_path: str) -> str:
    """rembg(AI 모델)로 배경을 지우고 투명 PNG로 저장한다."""
    with open(input_path, "rb") as input_file:
        input_bytes = input_file.read()

    output_bytes = remove(input_bytes)

    with open(output_path, "wb") as output_file:
        output_file.write(output_bytes)

    return output_path
