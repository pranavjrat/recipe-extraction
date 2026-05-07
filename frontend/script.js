const API_BASE_URL = 'http://localhost:8001';

const tabButtons = document.querySelectorAll('.tab-btn');
const tabPanes = document.querySelectorAll('.tab-pane');
const extractBtn = document.getElementById('extract-btn');
const recipeUrlInput = document.getElementById('recipe-url');
const recipeFallbackInput = document.getElementById('recipe-fallback');
const resultSection = document.getElementById('recipe-result');
const loading = document.getElementById('loading');
const errorBox = document.getElementById('error');
const historyLoading = document.getElementById('history-loading');
const historyTableBody = document.getElementById('history-tbody');
const noHistory = document.getElementById('no-history');
const historyCount = document.getElementById('history-count');
const modal = document.getElementById('details-modal');
const modalContent = document.getElementById('modal-content');
const modalClose = document.getElementById('modal-close');
const planBtn = document.getElementById('plan-btn');
const planResult = document.getElementById('plan-result');

tabButtons.forEach((button) => {
  button.addEventListener('click', () => {
    const target = button.dataset.tab;
    tabButtons.forEach((btn) => btn.classList.remove('active'));
    button.classList.add('active');
    tabPanes.forEach((pane) => pane.classList.remove('active'));
    document.getElementById(`${target}-tab`).classList.add('active');
    if (target === 'history') {
      loadHistory();
    }
  });
});

extractBtn.addEventListener('click', extractRecipe);
modalClose.addEventListener('click', closeModal);
planBtn.addEventListener('click', createMealPlan);
modal.addEventListener('click', (event) => {
  if (event.target === modal) closeModal();
});

async function extractRecipe() {
  const url = recipeUrlInput.value.trim();
  if (!url) {
    showError('Please enter a recipe URL.');
    return;
  }

  showError('');
  resultSection.classList.add('hidden');
  loading.classList.remove('hidden');

  try {
    const response = await fetch(`${API_BASE_URL}/api/extract`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url,
        raw_text: recipeFallbackInput.value.trim() || null,
        raw_html: recipeFallbackInput.value.trim().startsWith('<') ? recipeFallbackInput.value.trim() : null
      })
    });

    if (!response.ok) {
      const errorPayload = await response.json().catch(() => ({}));
      if (errorPayload.detail === 'Recipe Saved in History') {
        showError('Recipe Already Saved in History');
        loadHistory();
        return;
      }
      throw new Error(errorPayload.detail || 'Failed to extract recipe.');
    }

    const recipe = await response.json();
    renderRecipe(recipe);
  } catch (error) {
    showError(error.message);
  } finally {
    loading.classList.add('hidden');
  }
}

function renderRecipe(recipe) {
  const nutrition = recipe.nutrition_estimate || recipe.nutrition || {};
  resultSection.innerHTML = `
    <article class="card hero-card">
      <div class="card-heading">
        <div>
          <p class="eyebrow">Extracted Recipe</p>
          <h2>${escapeHtml(recipe.title || 'Untitled recipe')}</h2>
          <p class="muted">${escapeHtml(recipe.url || '')}</p>
        </div>
        <button class="secondary-btn" onclick="openDetails(${recipe.id})">View Details</button>
      </div>
      <div class="meta-grid">
        <div><span>Kitchen</span><strong>${escapeHtml(recipe.cuisine || 'Unknown')}</strong></div>
        <div><span>Prep</span><strong>${escapeHtml(recipe.prep_time || '-')}</strong></div>
        <div><span>Cook</span><strong>${escapeHtml(recipe.cook_time || '-')}</strong></div>
        <div><span>Total</span><strong>${escapeHtml(recipe.total_time || '-')}</strong></div>
        <div><span>Servings</span><strong>${escapeHtml(String(recipe.servings || '-'))}</strong></div>
        <div><span>Difficulty</span><strong>${escapeHtml(recipe.difficulty || '-')}</strong></div>
      </div>
    </article>

    <section class="grid-2">
      <article class="card">
        <h3>Ingredients</h3>
        ${renderIngredients(recipe.ingredients || [])}
      </article>
      <article class="card">
        <h3>Instructions</h3>
        ${renderInstructions(recipe.instructions || [])}
      </article>
    </section>

    <section class="grid-3">
      <article class="card">
        <h3>Nutrition Estimate</h3>
        ${renderNutrition(nutrition)}
      </article>
      <article class="card">
        <h3>Substitutions</h3>
        ${renderList(recipe.substitutions || [], 'No substitutions available.')}
      </article>
      <article class="card">
        <h3>Related Recipes</h3>
        ${renderList(recipe.related_recipes || [], 'No related recipes generated.')}
      </article>
    </section>

    <article class="card">
      <h3>Shopping List</h3>
      ${renderShoppingList(recipe.shopping_list || {})}
    </article>
  `;

  resultSection.classList.remove('hidden');
}

function renderIngredients(items) {
  if (!items.length) return '<p class="muted">No ingredients extracted.</p>';
  return `<ul class="bullet-list">${items.map((item) => `<li><strong>${escapeHtml(item.quantity || '')} ${escapeHtml(item.unit || '')}</strong> ${escapeHtml(item.item || '')}</li>`).join('')}</ul>`;
}

function renderInstructions(items) {
  if (!items.length) return '<p class="muted">No instructions extracted.</p>';
  return `<ol class="step-list">${items.map((step) => `<li>${escapeHtml(step)}</li>`).join('')}</ol>`;
}

function renderNutrition(nutrition) {
  const lines = [
    ['Calories', nutrition.calories ?? '-'],
    ['Protein', nutrition.protein ?? '-'],
    ['Carbs', nutrition.carbs ?? '-'],
    ['Fat', nutrition.fat ?? '-']
  ];
  return `<div class="nutrition-grid">${lines.map(([label, value]) => `<div><span>${label}</span><strong>${escapeHtml(String(value))}</strong></div>`).join('')}</div>`;
}

function renderList(items, emptyMessage) {
  if (!items.length) return `<p class="muted">${emptyMessage}</p>`;
  return `<ul class="bullet-list">${items.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul>`;
}

function renderShoppingList(list) {
  const categories = Object.entries(list);
  if (!categories.length) return '<p class="muted">No shopping list generated.</p>';
  return `<div class="shopping-columns">${categories.map(([category, items]) => `<div class="shopping-group"><h4>${escapeHtml(category)}</h4><ul class="bullet-list compact">${items.map((item) => `<li>${escapeHtml(item)}</li>`).join('')}</ul></div>`).join('')}</div>`;
}

async function loadHistory() {
  historyLoading.classList.remove('hidden');
  noHistory.classList.add('hidden');
  historyTableBody.innerHTML = '';

  try {
    const response = await fetch(`${API_BASE_URL}/api/recipes`);
    if (!response.ok) throw new Error('Failed to load history.');
    const recipes = await response.json();

    historyCount.textContent = `${recipes.length} saved recipes`;
    if (!recipes.length) {
      noHistory.classList.remove('hidden');
      return;
    }

    historyTableBody.innerHTML = recipes.map((recipe) => `
      <tr>
        <td><input type="checkbox" class="recipe-select" data-id="${recipe.id}" /></td>
        <td>${escapeHtml(recipe.title || 'Untitled')}</td>
        <td>${escapeHtml(recipe.cuisine || '-')}</td>
        <td><span class="difficulty ${escapeHtml((recipe.difficulty || 'unknown').toLowerCase())}">${escapeHtml(recipe.difficulty || '-')}</span></td>
        <td>${escapeHtml(formatDate(recipe.created_at))}</td>
        <td><button class="secondary-btn small" onclick="openDetails(${recipe.id})">Details</button></td>
      </tr>
    `).join('');
  } catch (error) {
    noHistory.textContent = error.message;
    noHistory.classList.remove('hidden');
  } finally {
    historyLoading.classList.add('hidden');
  }
}

async function openDetails(id) {
  const response = await fetch(`${API_BASE_URL}/api/recipes/${id}`);
  if (!response.ok) {
    showError('Failed to load recipe details.');
    return;
  }
  const recipe = await response.json();
  modalContent.innerHTML = buildModalMarkup(recipe);
  modal.classList.remove('hidden');
}

function buildModalMarkup(recipe) {
  const nutrition = recipe.nutrition_estimate || recipe.nutrition || {};
  return `
    <div class="modal-header">
      <div>
        <p class="eyebrow">Recipe Details</p>
        <h2 id="modal-title">${escapeHtml(recipe.title || 'Untitled recipe')}</h2>
      </div>
      <p class="muted">${escapeHtml(recipe.url || '')}</p>
    </div>
    <div class="grid-2 modal-grid">
      <article class="card subtle">
        <h3>Metadata</h3>
        ${renderMeta(recipe)}
      </article>
      <article class="card subtle">
        <h3>Nutrition</h3>
        ${renderNutrition(nutrition)}
      </article>
    </div>
    <div class="grid-2 modal-grid">
      <article class="card subtle"><h3>Ingredients</h3>${renderIngredients(recipe.ingredients || [])}</article>
      <article class="card subtle"><h3>Instructions</h3>${renderInstructions(recipe.instructions || [])}</article>
    </div>
    <div class="grid-2 modal-grid">
      <article class="card subtle"><h3>Substitutions</h3>${renderList(recipe.substitutions || [], 'No substitutions available.')}</article>
      <article class="card subtle"><h3>Related Recipes</h3>${renderList(recipe.related_recipes || [], 'No related recipes generated.')}</article>
    </div>
    <article class="card subtle"><h3>Shopping List</h3>${renderShoppingList(recipe.shopping_list || {})}</article>
  `;
}

function renderMeta(recipe) {
  const rows = [
    ['Cuisine', recipe.cuisine || '-'],
    ['Prep Time', recipe.prep_time || '-'],
    ['Cook Time', recipe.cook_time || '-'],
    ['Total Time', recipe.total_time || '-'],
    ['Servings', recipe.servings || '-'],
    ['Difficulty', recipe.difficulty || '-']
  ];
  return `<div class="meta-stack">${rows.map(([label, value]) => `<div><span>${label}</span><strong>${escapeHtml(String(value))}</strong></div>`).join('')}</div>`;
}

function closeModal() {
  modal.classList.add('hidden');
}

async function createMealPlan() {
  const selectedIds = Array.from(document.querySelectorAll('.recipe-select:checked')).map((checkbox) => Number(checkbox.dataset.id));
  if (selectedIds.length < 3) {
    planResult.innerHTML = '<p class="muted">Select at least 3 saved recipes to create a meal plan.</p>';
    planResult.classList.remove('hidden');
    return;
  }

  planResult.innerHTML = '<p class="muted">Generating meal plan...</p>';
  planResult.classList.remove('hidden');

  const response = await fetch(`${API_BASE_URL}/api/meal-plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ recipe_ids: selectedIds })
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    planResult.innerHTML = `<p class="muted">${escapeHtml(payload.detail || 'Failed to generate meal plan.')}</p>`;
    return;
  }

  const plan = await response.json();
  planResult.innerHTML = `
    <div class="meal-plan-grid">
      <div class="card subtle">
        <h3>Plan</h3>
        <ol class="step-list">${(plan.meal_plan || []).map((day) => `<li>Day ${escapeHtml(String(day.day))}: ${escapeHtml(day.recipe)}</li>`).join('')}</ol>
      </div>
      <div class="card subtle">
        <h3>Combined Shopping List</h3>
        ${renderShoppingList(plan.combined_shopping_list || {})}
      </div>
    </div>
  `;
}

function showError(message) {
  if (!message) {
    errorBox.classList.add('hidden');
    errorBox.textContent = '';
    return;
  }
  errorBox.textContent = message;
  errorBox.classList.remove('hidden');
}

function formatDate(value) {
  if (!value) return '-';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function escapeHtml(value) {
  return String(value)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

window.openDetails = openDetails;
