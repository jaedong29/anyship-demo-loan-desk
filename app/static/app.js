"use strict";
const byId = id => document.getElementById(id);
let currentItems = [];
let busy = false;
function message(text, error = false) {
  const node = byId("notice");
  node.textContent = text; node.className = error ? "error" : ""; node.hidden = false;
}
async function request(path, options = {}) {
  const response = await fetch(path, { ...options, headers: {"Content-Type": "application/json"} });
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === "string" ? data.detail : "입력한 이름과 수량을 확인해 주세요.");
  return data;
}
function element(tag, text, className) {
  const node = document.createElement(tag); if (text !== undefined) node.textContent = text;
  if (className) node.className = className; return node;
}
function renderItems(items) {
  const shelf = byId("items"); shelf.replaceChildren();
  const picker = byId("loan-item"); const previous = picker.value; picker.replaceChildren();
  picker.append(new Option("물품을 선택하세요", ""));
  byId("item-count").textContent = items.length;
  byId("available-count").textContent = items.reduce((sum, item) => sum + item.available, 0);
  byId("loan-count").textContent = items.reduce((sum, item) => sum + item.on_loan, 0);
  if (!items.length) shelf.append(element("p", "첫 번째 물품을 등록해 보세요. →", "empty"));
  items.forEach(item => {
    const card = element("article", undefined, "item");
    card.append(element("div", "▧", "item-icon"), element("h3", item.name));
    const stock = element("div", undefined, "stock");
    stock.append(element("span", `전체 ${item.total}개 · 대여 ${item.on_loan}개`), element("strong", `대여 가능 ${item.available}개`, item.available ? "" : "none"));
    const bar = element("div", undefined, "stock-bar"); const progress = element("span");
    progress.style.width = `${100 * item.available / item.total}%`; bar.append(progress);
    const button = element("button", item.available ? "이 물품 빌리기 ↗" : "모두 대여 중", "pick-button");
    button.type = "button"; button.disabled = busy || !item.available;
    button.addEventListener("click", () => { picker.value = String(item.id); byId("borrower").focus(); });
    card.append(stock, bar, button); shelf.append(card);
    if (item.available) picker.append(new Option(`${item.name} (${item.available}개 가능)`, String(item.id)));
  });
  if ([...picker.options].some(option => option.value === previous)) picker.value = previous;
}
function renderLoans(loans) {
  const body = byId("loans"); body.replaceChildren();
  if (!loans.length) { const row = element("tr"); const cell = element("td", "아직 대여 기록이 없어요. 물품을 빌려 보세요.", "empty"); cell.colSpan = 5; row.append(cell); body.append(row); }
  loans.forEach(loan => {
    const row = element("tr");
    row.append(element("td", loan.item_name), element("td", loan.borrower), element("td", new Date(loan.borrowed_at).toLocaleString("ko-KR", {month:"numeric", day:"numeric", hour:"2-digit", minute:"2-digit"}), "timestamp"));
    const status = element("td"); status.append(element("span", loan.returned_at ? "반납 완료" : "대여 중", loan.returned_at ? "badge returned" : "badge"));
    const action = element("td");
    if (!loan.returned_at) {
      const button = element("button", "반납하기", "return-button"); button.type = "button"; button.disabled = busy;
      button.setAttribute("aria-label", `${loan.borrower}의 ${loan.item_name} 반납`);
      button.addEventListener("click", () => perform(async () => { await request(`/api/loans/${loan.id}/return`, {method:"POST"}); message("반납했어요. 다음 사람도 빌릴 수 있어요."); }));
      action.append(button);
    } else action.append(element("span", "—", "timestamp"));
    row.append(status, action); body.append(row);
  });
}
async function refresh() {
  const [items, loans] = await Promise.all([request("/api/items"), request("/api/loans")]);
  currentItems = items; renderItems(items); renderLoans(loans);
}
async function perform(action) {
  if (busy) return; busy = true; document.querySelectorAll("button").forEach(button => button.disabled = true);
  try { await action(); await refresh(); } catch (error) { message(error.message || "서버에 연결하지 못했어요.", true); }
  finally {
    busy = false; document.querySelectorAll("button").forEach(button => button.disabled = false);
    renderItems(currentItems);
  }
}
byId("item-form").addEventListener("submit", event => {
  event.preventDefault(); const name = byId("item-name").value.trim(); const total = Number(byId("item-total").value);
  perform(async () => { await request("/api/items", {method:"POST", body:JSON.stringify({name,total})}); byId("item-form").reset(); message(`물품함에 등록했어요: ${name}`); });
});
byId("loan-form").addEventListener("submit", event => {
  event.preventDefault(); const item_id = Number(byId("loan-item").value); const borrower = byId("borrower").value.trim();
  perform(async () => { await request("/api/loans", {method:"POST", body:JSON.stringify({item_id,borrower})}); byId("borrower").value = ""; message("대여 기록을 남겼어요. 잘 사용하고 돌려주세요!"); });
});
byId("refresh").addEventListener("click", () => perform(async () => {}));
refresh().catch(error => message(error.message || "서버에 연결하지 못했어요.", true));
