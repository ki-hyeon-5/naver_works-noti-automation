"use strict";

const search = document.getElementById("manual-search");
const sections = Array.from(document.querySelectorAll(".manual-section"));
const count = document.getElementById("search-count");
const empty = document.getElementById("no-results");
const links = Array.from(document.querySelectorAll(".sidebar nav a"));

function normalize(value) {
  return value.toLocaleLowerCase("ko").replace(/\s+/g, " ").trim();
}

function filterSections() {
  const terms = normalize(search.value).split(" ").filter(Boolean);
  let visible = 0;
  for (const section of sections) {
    const haystack = normalize(section.dataset.title + " " + section.textContent);
    const match = terms.every(term => haystack.includes(term));
    section.hidden = !match;
    if (match) visible += 1;
  }
  for (const link of links) {
    const target = document.getElementById(link.hash.slice(1));
    link.parentElement.hidden = Boolean(target && target.hidden);
  }
  count.textContent = `${visible}개 섹션`;
  empty.hidden = visible !== 0;
}

search.addEventListener("input", filterSections);
filterSections();
