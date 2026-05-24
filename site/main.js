(function () {
  "use strict";

  var STORAGE_KEY = "cdag_theme";
  var THEMES = { light: true, dark: true };

  function safeStorage() {
    try {
      return window.localStorage;
    } catch (error) {
      return null;
    }
  }

  function getStoredTheme() {
    var storage = safeStorage();
    if (!storage) {
      return null;
    }
    var value = storage.getItem(STORAGE_KEY);
    return THEMES[value] ? value : null;
  }

  function setStoredTheme(theme) {
    var storage = safeStorage();
    if (!storage) {
      return;
    }
    try {
      storage.setItem(STORAGE_KEY, theme);
    } catch (error) {
      // Ignore storage write failures.
    }
  }

  function systemTheme() {
    if (!window.matchMedia) {
      return "dark";
    }
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function themeToggle() {
    return document.querySelector("[data-theme-toggle]") || document.getElementById("theme-toggle");
  }

  function labelNodes() {
    return document.querySelectorAll("[data-theme-label], #theme-label, #theme-toggle-label");
  }

  function updateToggle(theme) {
    var toggle = themeToggle();
    var nextTheme = theme === "dark" ? "light" : "dark";
    var titleCase = theme.charAt(0).toUpperCase() + theme.slice(1);

    if (toggle) {
      toggle.setAttribute("aria-pressed", theme === "dark" ? "true" : "false");
      toggle.setAttribute("aria-label", "Switch to " + nextTheme + " theme");
      toggle.setAttribute("title", "Switch to " + nextTheme + " theme");
    }

    var nodes = labelNodes();
    if (nodes.length) {
      nodes.forEach(function (node) {
        node.textContent = titleCase;
      });
    }
  }

  function applyTheme(theme, persist) {
    var selected = THEMES[theme] ? theme : systemTheme();
    document.documentElement.dataset.theme = selected;
    document.documentElement.style.colorScheme = selected;
    updateToggle(selected);

    if (persist) {
      setStoredTheme(selected);
    }
    return selected;
  }

  function bindThemeToggle() {
    var toggle = themeToggle();
    if (!toggle) {
      return;
    }

    toggle.addEventListener("click", function () {
      var current = document.documentElement.dataset.theme || systemTheme();
      var next = current === "dark" ? "light" : "dark";
      applyTheme(next, true);
    });

    if (toggle.tagName !== "BUTTON") {
      toggle.setAttribute("role", "button");
      if (!toggle.hasAttribute("tabindex")) {
        toggle.setAttribute("tabindex", "0");
      }
      toggle.addEventListener("keydown", function (event) {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          toggle.click();
        }
      });
    }
  }

  function bindSystemSync() {
    if (!window.matchMedia) {
      return;
    }
    var media = window.matchMedia("(prefers-color-scheme: dark)");
    var handler = function (event) {
      if (getStoredTheme()) {
        return;
      }
      applyTheme(event.matches ? "dark" : "light", false);
    };

    if (typeof media.addEventListener === "function") {
      media.addEventListener("change", handler);
    } else if (typeof media.addListener === "function") {
      media.addListener(handler);
    }
  }

  function bindAccordion() {
    var triggers = document.querySelectorAll("[data-acc-trigger]");
    if (!triggers.length) {
      return;
    }

    function setItemState(trigger, open) {
      var targetId = trigger.getAttribute("aria-controls");
      if (!targetId) {
        return;
      }
      var panel = document.getElementById(targetId);
      if (!panel) {
        return;
      }
      trigger.setAttribute("aria-expanded", open ? "true" : "false");
      panel.hidden = !open;

      var mark = trigger.querySelector(".acc-mark");
      if (mark) {
        mark.textContent = open ? "−" : "+";
      }
    }

    triggers.forEach(function (trigger) {
      trigger.addEventListener("click", function () {
        var expanded = trigger.getAttribute("aria-expanded") === "true";
        if (expanded) {
          return;
        }

        triggers.forEach(function (otherTrigger) {
          if (otherTrigger !== trigger) {
            setItemState(otherTrigger, false);
          }
        });
        setItemState(trigger, true);
      });
    });

    triggers.forEach(function (trigger, index) {
      setItemState(trigger, index === 0);
    });
  }

  function animateCount(node) {
    var target = Number(node.getAttribute("data-count-to"));
    if (!Number.isFinite(target)) {
      return;
    }
    if (node.getAttribute("data-counted") === "true") {
      return;
    }
    node.setAttribute("data-counted", "true");

    var decimals = Number(node.getAttribute("data-count-decimals") || "0");
    var suffix = node.getAttribute("data-count-suffix") || "";
    var duration = 1100;
    var start = performance.now();

    function step(now) {
      var progress = Math.min((now - start) / duration, 1);
      var eased = 1 - Math.pow(1 - progress, 3);
      var value = target * eased;
      var text = value.toFixed(decimals);
      if (decimals === 0) {
        text = String(Math.round(value));
      }
      node.textContent = text + suffix;
      if (progress < 1) {
        requestAnimationFrame(step);
      } else {
        node.textContent = decimals > 0 ? target.toFixed(decimals) + suffix : String(Math.round(target)) + suffix;
      }
    }

    requestAnimationFrame(step);
  }

  function initMetricCountUp() {
    var nodes = document.querySelectorAll("[data-count-to]");
    if (!nodes.length) {
      return;
    }

    if (!("IntersectionObserver" in window)) {
      nodes.forEach(animateCount);
      return;
    }

    var observer = new IntersectionObserver(
      function (entries, obs) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            animateCount(entry.target);
            obs.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.35 }
    );

    nodes.forEach(function (node) {
      observer.observe(node);
    });
  }

  function init() {
    applyTheme(getStoredTheme() || systemTheme(), false);
    bindThemeToggle();
    bindSystemSync();
    bindAccordion();
    initMetricCountUp();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
