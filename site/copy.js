const copyButton = document.querySelector("#copy");

if (copyButton) {
  const shareText = document.querySelector("#share-text");
  const status = document.querySelector("#copy-status");
  copyButton.hidden = false;

  copyButton.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(shareText.value);
      shareText.hidden = true;
      status.textContent = "공유 문구를 복사했습니다.";
    } catch {
      shareText.hidden = false;
      shareText.focus();
      shareText.select();
      status.textContent = "선택된 문구를 직접 복사할 수 있습니다.";
    }
  });
}
