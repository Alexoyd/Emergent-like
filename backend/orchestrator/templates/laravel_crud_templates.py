"""
Templates Laravel CRUD Complets - Style Emergent.sh

Ces templates garantissent la génération d'applications Laravel COMPLÈTES et FONCTIONNELLES
dès la première génération, sans nécessiter d'intervention manuelle.

Philosophie "Zero Config" : L'application doit démarrer IMMÉDIATEMENT après génération.
"""

def get_controller_template(model_name: str, model_plural: str) -> str:
    """
    Génère un Controller Laravel COMPLET avec les 7 méthodes Resource.
    
    Args:
        model_name: Nom du modèle singulier (ex: "Game")
        model_plural: Nom pluriel pour les routes/vues (ex: "games")
    
    Returns:
        Code PHP complet du controller
    """
    model_lower = model_name.lower()
    
    return f'''<?php

namespace App\\Http\\Controllers;

use App\\Models\\{model_name};
use Illuminate\\Http\\Request;

class {model_name}Controller extends Controller
{{
    /**
     * Display a listing of the resource.
     */
    public function index()
    {{
        ${model_plural} = {model_name}::latest()->paginate(10);
        
        return view('{model_plural}.index', compact('{model_plural}'));
    }}

    /**
     * Show the form for creating a new resource.
     */
    public function create()
    {{
        return view('{model_plural}.create');
    }}

    /**
     * Store a newly created resource in storage.
     */
    public function store(Request $request)
    {{
        $validated = $request->validate([
            // TODO: Add validation rules based on your model fields
            // Example:
            // 'name' => 'required|string|max:255',
            // 'description' => 'nullable|string',
        ]);

        {model_name}::create($validated);

        return redirect()->route('{model_plural}.index')
            ->with('success', '{model_name} créé avec succès !');
    }}

    /**
     * Display the specified resource.
     */
    public function show({model_name} ${model_lower})
    {{
        return view('{model_plural}.show', compact('{model_lower}'));
    }}

    /**
     * Show the form for editing the specified resource.
     */
    public function edit({model_name} ${model_lower})
    {{
        return view('{model_plural}.edit', compact('{model_lower}'));
    }}

    /**
     * Update the specified resource in storage.
     */
    public function update(Request $request, {model_name} ${model_lower})
    {{
        $validated = $request->validate([
            // TODO: Add validation rules based on your model fields
            // Example:
            // 'name' => 'required|string|max:255',
            // 'description' => 'nullable|string',
        ]);

        ${model_lower}->update($validated);

        return redirect()->route('{model_plural}.index')
            ->with('success', '{model_name} mis à jour avec succès !');
    }}

    /**
     * Remove the specified resource from storage.
     */
    public function destroy({model_name} ${model_lower})
    {{
        ${model_lower}->delete();

        return redirect()->route('{model_plural}.index')
            ->with('success', '{model_name} supprimé avec succès !');
    }}
}}
'''


def get_model_template(model_name: str, table_name: str) -> str:
    """
    Génère un Model Laravel avec Eloquent.
    
    Args:
        model_name: Nom du modèle (ex: "Game")
        table_name: Nom de la table (ex: "games")
    
    Returns:
        Code PHP du model
    """
    return f'''<?php

namespace App\\Models;

use Illuminate\\Database\\Eloquent\\Factories\\HasFactory;
use Illuminate\\Database\\Eloquent\\Model;

class {model_name} extends Model
{{
    use HasFactory;

    protected $table = '{table_name}';

    /**
     * The attributes that are mass assignable.
     *
     * @var array<int, string>
     */
    protected $fillable = [
        // TODO: Add your model's fillable fields
        // Example:
        // 'name',
        // 'description',
    ];

    /**
     * The attributes that should be cast.
     *
     * @var array<string, string>
     */
    protected $casts = [
        // Example:
        // 'published_at' => 'datetime',
    ];
}}
'''


def get_migration_template(table_name: str) -> str:
    """
    Génère une Migration Laravel.
    
    Args:
        table_name: Nom de la table (ex: "games")
    
    Returns:
        Code PHP de la migration
    """
    class_name = ''.join(word.capitalize() for word in table_name.split('_'))
    
    return f'''<?php

use Illuminate\\Database\\Migrations\\Migration;
use Illuminate\\Database\\Schema\\Blueprint;
use Illuminate\\Support\\Facades\\Schema;

return new class extends Migration
{{
    /**
     * Run the migrations.
     */
    public function up(): void
    {{
        Schema::create('{table_name}', function (Blueprint $table) {{
            $table->id();
            
            // TODO: Add your table columns here
            // Example:
            // $table->string('name');
            // $table->text('description')->nullable();
            
            $table->timestamps();
        }});
    }}

    /**
     * Reverse the migrations.
     */
    public function down(): void
    {{
        Schema::dropIfExists('{table_name}');
    }}
}};
'''


def get_layout_template() -> str:
    """
    Génère le layout Blade principal avec Tailwind CSS et design moderne.
    
    Returns:
        Code HTML/Blade du layout
    """
    return '''<!DOCTYPE html>
<html lang="{{ str_replace('_', '-', app()->getLocale()) }}">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="csrf-token" content="{{ csrf_token() }}">

    <title>{{ config('app.name', 'Laravel') }}</title>

    <!-- Fonts -->
    <link rel="preconnect" href="https://fonts.bunny.net">
    <link href="https://fonts.bunny.net/css?family=figtree:400,500,600&display=swap" rel="stylesheet" />

    <!-- Styles / Scripts -->
    @if (file_exists(public_path('build/manifest.json')) || file_exists(public_path('hot')))
        @vite(['resources/css/app.css', 'resources/js/app.js'])
    @else
        <link href="{{ asset('css/app.css') }}" rel="stylesheet">
    @endif
</head>
<body class="bg-gray-50 font-sans antialiased">
    <div class="min-h-screen">
        <!-- Navigation -->
        <nav class="bg-white shadow-sm border-b border-gray-200">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                <div class="flex justify-between h-16">
                    <div class="flex">
                        <!-- Logo -->
                        <div class="flex-shrink-0 flex items-center">
                            <a href="{{ url('/') }}" class="text-xl font-bold text-gray-900">
                                {{ config('app.name', 'Laravel') }}
                            </a>
                        </div>

                        <!-- Navigation Links -->
                        <div class="hidden space-x-8 sm:-my-px sm:ml-10 sm:flex">
                            @yield('navigation')
                        </div>
                    </div>
                </div>
            </div>
        </nav>

        <!-- Page Heading -->
        @if (isset($header))
            <header class="bg-white shadow">
                <div class="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
                    {{ $header }}
                </div>
            </header>
        @endif

        <!-- Flash Messages -->
        @if (session('success'))
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-4">
                <div class="bg-green-50 border-l-4 border-green-400 p-4 rounded-md">
                    <div class="flex">
                        <div class="flex-shrink-0">
                            <svg class="h-5 w-5 text-green-400" viewBox="0 0 20 20" fill="currentColor">
                                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm3.707-9.293a1 1 0 00-1.414-1.414L9 10.586 7.707 9.293a1 1 0 00-1.414 1.414l2 2a1 1 0 001.414 0l4-4z" clip-rule="evenodd"/>
                            </svg>
                        </div>
                        <div class="ml-3">
                            <p class="text-sm font-medium text-green-800">
                                {{ session('success') }}
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        @endif

        @if (session('error'))
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-4">
                <div class="bg-red-50 border-l-4 border-red-400 p-4 rounded-md">
                    <div class="flex">
                        <div class="flex-shrink-0">
                            <svg class="h-5 w-5 text-red-400" viewBox="0 0 20 20" fill="currentColor">
                                <path fill-rule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clip-rule="evenodd"/>
                            </svg>
                        </div>
                        <div class="ml-3">
                            <p class="text-sm font-medium text-red-800">
                                {{ session('error') }}
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        @endif

        <!-- Page Content -->
        <main class="py-8">
            <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
                @yield('content')
            </div>
        </main>
    </div>
</body>
</html>
'''


def get_index_view_template(model_plural: str, model_name: str) -> str:
    """
    Génère la vue index.blade.php (liste avec pagination).
    
    Args:
        model_plural: Nom pluriel (ex: "games")
        model_name: Nom singulier du modèle (ex: "Game")
    
    Returns:
        Code Blade de la vue index
    """
    model_lower = model_name.lower()
    
    return f'''@extends('layouts.app')

@section('content')
<div class="bg-white rounded-lg shadow-md">
    <!-- Header -->
    <div class="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
        <h1 class="text-2xl font-bold text-gray-900">Liste des {model_plural}</h1>
        <a href="{{{{ route('{model_plural}.create') }}}}" 
           class="inline-flex items-center px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition duration-150 ease-in-out">
            <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
            </svg>
            Nouveau {model_name}
        </a>
    </div>

    <!-- Table -->
    @if(${model_plural}->count() > 0)
        <div class="overflow-x-auto">
            <table class="min-w-full divide-y divide-gray-200">
                <thead class="bg-gray-50">
                    <tr>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            ID
                        </th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Nom
                        </th>
                        <th scope="col" class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Date de création
                        </th>
                        <th scope="col" class="px-6 py-3 text-right text-xs font-medium text-gray-500 uppercase tracking-wider">
                            Actions
                        </th>
                    </tr>
                </thead>
                <tbody class="bg-white divide-y divide-gray-200">
                    @foreach(${model_plural} as ${model_lower})
                        <tr class="hover:bg-gray-50 transition duration-150">
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                                {{{{ ${model_lower}->id }}}}
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                                {{{{ ${model_lower}->name ?? 'N/A' }}}}
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                                {{{{ ${model_lower}->created_at->format('d/m/Y H:i') }}}}
                            </td>
                            <td class="px-6 py-4 whitespace-nowrap text-right text-sm font-medium space-x-2">
                                <a href="{{{{ route('{model_plural}.show', ${model_lower}) }}}}" 
                                   class="text-blue-600 hover:text-blue-900">
                                    Voir
                                </a>
                                <a href="{{{{ route('{model_plural}.edit', ${model_lower}) }}}}" 
                                   class="text-indigo-600 hover:text-indigo-900">
                                    Modifier
                                </a>
                                <form action="{{{{ route('{model_plural}.destroy', ${model_lower}) }}}}" 
                                      method="POST" 
                                      class="inline"
                                      onsubmit="return confirm('Êtes-vous sûr de vouloir supprimer cet élément ?');">
                                    @csrf
                                    @method('DELETE')
                                    <button type="submit" class="text-red-600 hover:text-red-900">
                                        Supprimer
                                    </button>
                                </form>
                            </td>
                        </tr>
                    @endforeach
                </tbody>
            </table>
        </div>

        <!-- Pagination -->
        <div class="px-6 py-4 border-t border-gray-200">
            {{{{ ${model_plural}->links() }}}}
        </div>
    @else
        <div class="px-6 py-12 text-center">
            <svg class="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 13V6a2 2 0 00-2-2H6a2 2 0 00-2 2v7m16 0v5a2 2 0 01-2 2H6a2 2 0 01-2-2v-5m16 0h-2.586a1 1 0 00-.707.293l-2.414 2.414a1 1 0 01-.707.293h-3.172a1 1 0 01-.707-.293l-2.414-2.414A1 1 0 006.586 13H4"/>
            </svg>
            <h3 class="mt-2 text-sm font-medium text-gray-900">Aucun {model_name}</h3>
            <p class="mt-1 text-sm text-gray-500">Commencez par créer un nouveau {model_name}.</p>
            <div class="mt-6">
                <a href="{{{{ route('{model_plural}.create') }}}}" 
                   class="inline-flex items-center px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg">
                    <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
                    </svg>
                    Créer un {model_name}
                </a>
            </div>
        </div>
    @endif
</div>
@endsection
'''


def get_create_view_template(model_plural: str, model_name: str) -> str:
    """
    Génère la vue create.blade.php (formulaire de création).
    
    Args:
        model_plural: Nom pluriel (ex: "games")
        model_name: Nom singulier du modèle (ex: "Game")
    
    Returns:
        Code Blade de la vue create
    """
    return f'''@extends('layouts.app')

@section('content')
<div class="max-w-2xl mx-auto">
    <div class="bg-white rounded-lg shadow-md">
        <!-- Header -->
        <div class="px-6 py-4 border-b border-gray-200">
            <h1 class="text-2xl font-bold text-gray-900">Créer un nouveau {model_name}</h1>
        </div>

        <!-- Form -->
        <form action="{{{{ route('{model_plural}.store') }}}}" method="POST" class="px-6 py-4 space-y-6">
            @csrf

            <!-- TODO: Add your form fields here -->
            <!-- Example field: -->
            <div>
                <label for="name" class="block text-sm font-medium text-gray-700 mb-2">
                    Nom <span class="text-red-500">*</span>
                </label>
                <input type="text" 
                       name="name" 
                       id="name" 
                       value="{{{{ old('name') }}}}"
                       class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 @error('name') border-red-500 @enderror"
                       required>
                @error('name')
                    <p class="mt-1 text-sm text-red-600">{{{{ $message }}}}</p>
                @enderror
            </div>

            <div>
                <label for="description" class="block text-sm font-medium text-gray-700 mb-2">
                    Description
                </label>
                <textarea name="description" 
                          id="description" 
                          rows="4"
                          class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 @error('description') border-red-500 @enderror">{{{{ old('description') }}}}</textarea>
                @error('description')
                    <p class="mt-1 text-sm text-red-600">{{{{ $message }}}}</p>
                @enderror
            </div>

            <!-- Actions -->
            <div class="flex items-center justify-end space-x-3 pt-4 border-t border-gray-200">
                <a href="{{{{ route('{model_plural}.index') }}}}" 
                   class="px-4 py-2 bg-gray-200 hover:bg-gray-300 text-gray-800 font-semibold rounded-lg transition duration-150">
                    Annuler
                </a>
                <button type="submit" 
                        class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition duration-150">
                    Créer
                </button>
            </div>
        </form>
    </div>
</div>
@endsection
'''


def get_edit_view_template(model_plural: str, model_name: str) -> str:
    """
    Génère la vue edit.blade.php (formulaire d'édition).
    
    Args:
        model_plural: Nom pluriel (ex: "games")
        model_name: Nom singulier du modèle (ex: "Game")
    
    Returns:
        Code Blade de la vue edit
    """
    model_lower = model_name.lower()
    
    return f'''@extends('layouts.app')

@section('content')
<div class="max-w-2xl mx-auto">
    <div class="bg-white rounded-lg shadow-md">
        <!-- Header -->
        <div class="px-6 py-4 border-b border-gray-200">
            <h1 class="text-2xl font-bold text-gray-900">Modifier le {model_name}</h1>
        </div>

        <!-- Form -->
        <form action="{{{{ route('{model_plural}.update', ${model_lower}) }}}}" method="POST" class="px-6 py-4 space-y-6">
            @csrf
            @method('PUT')

            <!-- TODO: Add your form fields here -->
            <!-- Example field: -->
            <div>
                <label for="name" class="block text-sm font-medium text-gray-700 mb-2">
                    Nom <span class="text-red-500">*</span>
                </label>
                <input type="text" 
                       name="name" 
                       id="name" 
                       value="{{{{ old('name', ${model_lower}->name) }}}}"
                       class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 @error('name') border-red-500 @enderror"
                       required>
                @error('name')
                    <p class="mt-1 text-sm text-red-600">{{{{ $message }}}}</p>
                @enderror
            </div>

            <div>
                <label for="description" class="block text-sm font-medium text-gray-700 mb-2">
                    Description
                </label>
                <textarea name="description" 
                          id="description" 
                          rows="4"
                          class="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 @error('description') border-red-500 @enderror">{{{{ old('description', ${model_lower}->description) }}}}</textarea>
                @error('description')
                    <p class="mt-1 text-sm text-red-600">{{{{ $message }}}}</p>
                @enderror
            </div>

            <!-- Actions -->
            <div class="flex items-center justify-end space-x-3 pt-4 border-t border-gray-200">
                <a href="{{{{ route('{model_plural}.index') }}}}" 
                   class="px-4 py-2 bg-gray-200 hover:bg-gray-300 text-gray-800 font-semibold rounded-lg transition duration-150">
                    Annuler
                </a>
                <button type="submit" 
                        class="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white font-semibold rounded-lg transition duration-150">
                    Mettre à jour
                </button>
            </div>
        </form>
    </div>
</div>
@endsection
'''


def get_show_view_template(model_plural: str, model_name: str) -> str:
    """
    Génère la vue show.blade.php (affichage des détails).
    
    Args:
        model_plural: Nom pluriel (ex: "games")
        model_name: Nom singulier du modèle (ex: "Game")
    
    Returns:
        Code Blade de la vue show
    """
    model_lower = model_name.lower()
    
    return f'''@extends('layouts.app')

@section('content')
<div class="max-w-3xl mx-auto">
    <div class="bg-white rounded-lg shadow-md">
        <!-- Header -->
        <div class="px-6 py-4 border-b border-gray-200 flex justify-between items-center">
            <h1 class="text-2xl font-bold text-gray-900">Détails du {model_name}</h1>
            <div class="flex space-x-2">
                <a href="{{{{ route('{model_plural}.edit', ${model_lower}) }}}}" 
                   class="inline-flex items-center px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold rounded-lg transition duration-150">
                    <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>
                    </svg>
                    Modifier
                </a>
                <a href="{{{{ route('{model_plural}.index') }}}}" 
                   class="inline-flex items-center px-4 py-2 bg-gray-200 hover:bg-gray-300 text-gray-800 font-semibold rounded-lg transition duration-150">
                    Retour à la liste
                </a>
            </div>
        </div>

        <!-- Content -->
        <div class="px-6 py-4 space-y-6">
            <!-- TODO: Add your model fields here -->
            <!-- Example fields: -->
            <div>
                <h3 class="text-sm font-medium text-gray-500 uppercase tracking-wider mb-2">ID</h3>
                <p class="text-lg text-gray-900">{{{{ ${model_lower}->id }}}}</p>
            </div>

            <div>
                <h3 class="text-sm font-medium text-gray-500 uppercase tracking-wider mb-2">Nom</h3>
                <p class="text-lg text-gray-900">{{{{ ${model_lower}->name ?? 'N/A' }}}}</p>
            </div>

            <div>
                <h3 class="text-sm font-medium text-gray-500 uppercase tracking-wider mb-2">Description</h3>
                <p class="text-lg text-gray-900">{{{{ ${model_lower}->description ?? 'Aucune description' }}}}</p>
            </div>

            <div class="grid grid-cols-2 gap-6 pt-4 border-t border-gray-200">
                <div>
                    <h3 class="text-sm font-medium text-gray-500 uppercase tracking-wider mb-2">Date de création</h3>
                    <p class="text-lg text-gray-900">{{{{ ${model_lower}->created_at->format('d/m/Y à H:i') }}}}</p>
                </div>

                <div>
                    <h3 class="text-sm font-medium text-gray-500 uppercase tracking-wider mb-2">Dernière modification</h3>
                    <p class="text-lg text-gray-900">{{{{ ${model_lower}->updated_at->format('d/m/Y à H:i') }}}}</p>
                </div>
            </div>
        </div>

        <!-- Actions -->
        <div class="px-6 py-4 bg-gray-50 border-t border-gray-200 flex justify-between items-center">
            <form action="{{{{ route('{model_plural}.destroy', ${model_lower}) }}}}" 
                  method="POST"
                  onsubmit="return confirm('Êtes-vous sûr de vouloir supprimer cet élément ? Cette action est irréversible.');">
                @csrf
                @method('DELETE')
                <button type="submit" 
                        class="inline-flex items-center px-4 py-2 bg-red-600 hover:bg-red-700 text-white font-semibold rounded-lg transition duration-150">
                    <svg class="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                    </svg>
                    Supprimer
                </button>
            </form>
        </div>
    </div>
</div>
@endsection
'''


def get_routes_example(model_plural: str, model_name: str) -> str:
    """
    Génère l'exemple de routes à ajouter dans web.php.
    
    Args:
        model_plural: Nom pluriel (ex: "games")
        model_name: Nom singulier du modèle (ex: "Game")
    
    Returns:
        Code PHP des routes
    """
    return f'''
// Routes pour {model_name} CRUD
Route::resource('{model_plural}', App\\Http\\Controllers\\{model_name}Controller::class);
'''


def get_crud_guidelines_for_prompt() -> str:
    """
    Retourne les guidelines ultra-détaillées pour le prompt LLM.
    
    Ces guidelines forcent le LLM à générer TOUS les fichiers nécessaires
    pour un CRUD complet et fonctionnel.
    
    Returns:
        Texte des guidelines à inclure dans le prompt
    """
    return """
🔥🔥🔥 PROTOCOLE CRUD COMPLET LARAVEL - OBLIGATOIRE 🔥🔥🔥

Quand une feature nécessite un CRUD (ex: "gestion de produits", "système de jeux", etc.),
vous DEVEZ générer TOUS les fichiers suivants EN UNE SEULE FOIS :

═══════════════════════════════════════════════════════════════════
📋 CHECKLIST OBLIGATOIRE (TOUS CES FICHIERS DOIVENT ÊTRE CRÉÉS)
═══════════════════════════════════════════════════════════════════

1. ✅ MIGRATION (database/migrations/YYYY_MM_DD_HHMMSS_create_[table]_table.php)
   → Créer la table avec Schema::create()
   → Ajouter timestamps(), id(), et tous les champs nécessaires

2. ✅ MODEL (app/Models/[ModelName].php)
   → Définir $fillable avec TOUS les champs de la table
   → Hériter de Model avec HasFactory

3. ✅ CONTROLLER COMPLET (app/Http/Controllers/[ModelName]Controller.php)
   → LES 7 MÉTHODES OBLIGATOIRES :
     • index() : Liste paginée avec paginate(10)
     • create() : Formulaire de création
     • store() : Validation + création + redirect avec message success
     • show() : Affichage d'un élément
     • edit() : Formulaire d'édition
     • update() : Validation + mise à jour + redirect
     • destroy() : Suppression + redirect

4. ✅ ROUTES (routes/web.php)
   → Ajouter Route::resource('[plural]', [ModelName]Controller::class);
   → SI c'est le premier CRUD : modifier route '/' pour rediriger vers [plural].index
   
5. ✅ LAYOUT (resources/views/layouts/app.blade.php) - SI PAS DÉJÀ CRÉÉ
   → Layout avec Tailwind CSS
   → Navigation
   → Flash messages (success/error)
   → Responsive

6. ✅ VUE INDEX (resources/views/[plural]/index.blade.php)
   → Liste paginée des éléments
   → Bouton "Créer nouveau"
   → Actions : Voir, Modifier, Supprimer
   → Message si liste vide

7. ✅ VUE CREATE (resources/views/[plural]/create.blade.php)
   → Formulaire de création avec @csrf
   → Tous les champs du model
   → Validation errors avec @error
   → Boutons Créer et Annuler

8. ✅ VUE EDIT (resources/views/[plural]/edit.blade.php)
   → Formulaire d'édition avec @csrf + @method('PUT')
   → Champs pré-remplis avec old() et valeurs actuelles
   → Validation errors
   → Boutons Mettre à jour et Annuler

9. ✅ VUE SHOW (resources/views/[plural]/show.blade.php)
   → Affichage détaillé de l'élément
   → Boutons Modifier et Supprimer
   → Lien retour à la liste

═══════════════════════════════════════════════════════════════════
🚨 RÈGLES CRITIQUES - ÉCHEC SI NON RESPECTÉES
═══════════════════════════════════════════════════════════════════

❌ INTERDIT :
• Créer seulement le Controller sans les vues → ÉCHEC
• Créer seulement le Model sans le Controller → ÉCHEC
• Oublier la migration → ÉCHEC
• Controller avec moins de 7 méthodes → ÉCHEC
• Créer moins de 4 vues (index, create, edit, show) → ÉCHEC
• Ne pas ajouter les routes → ÉCHEC

✅ OBLIGATOIRE :
• TOUTES les 9 opérations ci-dessus doivent être dans votre JSON
• Le Controller doit avoir exactement 7 méthodes Resource
• Les vues doivent utiliser Tailwind CSS pour le styling
• Les routes doivent utiliser Route::resource()
• Flash messages de succès après create/update/delete
• Pagination dans index() avec ->paginate(10)

═══════════════════════════════════════════════════════════════════
📝 TEMPLATE D'OPÉRATIONS JSON POUR CRUD COMPLET
═══════════════════════════════════════════════════════════════════

Exemple concret pour "Game CRUD" :

{
  "operations": [
    {
      "type": "create",
      "path": "database/migrations/2024_01_15_100000_create_games_table.php",
      "content": "<?php\\n\\nuse Illuminate\\Database\\Migrations\\Migration;\\nuse Illuminate\\Database\\Schema\\Blueprint;\\nuse Illuminate\\Support\\Facades\\Schema;\\n\\nreturn new class extends Migration\\n{\\n    public function up(): void\\n    {\\n        Schema::create('games', function (Blueprint $table) {\\n            $table->id();\\n            $table->string('name');\\n            $table->text('description')->nullable();\\n            $table->integer('card_count')->default(0);\\n            $table->timestamps();\\n        });\\n    }\\n\\n    public function down(): void\\n    {\\n        Schema::dropIfExists('games');\\n    }\\n};\\n"
    },
    {
      "type": "create",
      "path": "app/Models/Game.php",
      "content": "<?php\\n\\nnamespace App\\Models;\\n\\nuse Illuminate\\Database\\Eloquent\\Factories\\HasFactory;\\nuse Illuminate\\Database\\Eloquent\\Model;\\n\\nclass Game extends Model\\n{\\n    use HasFactory;\\n\\n    protected $fillable = [\\n        'name',\\n        'description',\\n        'card_count',\\n    ];\\n}\\n"
    },
    {
      "type": "create",
      "path": "app/Http/Controllers/GameController.php",
      "content": "<?php\\n\\nnamespace App\\Http\\Controllers;\\n\\nuse App\\Models\\Game;\\nuse Illuminate\\Http\\Request;\\n\\nclass GameController extends Controller\\n{\\n    public function index()\\n    {\\n        $games = Game::latest()->paginate(10);\\n        return view('games.index', compact('games'));\\n    }\\n\\n    public function create()\\n    {\\n        return view('games.create');\\n    }\\n\\n    public function store(Request $request)\\n    {\\n        $validated = $request->validate([\\n            'name' => 'required|string|max:255',\\n            'description' => 'nullable|string',\\n            'card_count' => 'required|integer|min:0',\\n        ]);\\n\\n        Game::create($validated);\\n\\n        return redirect()->route('games.index')\\n            ->with('success', 'Jeu créé avec succès !');\\n    }\\n\\n    public function show(Game $game)\\n    {\\n        return view('games.show', compact('game'));\\n    }\\n\\n    public function edit(Game $game)\\n    {\\n        return view('games.edit', compact('game'));\\n    }\\n\\n    public function update(Request $request, Game $game)\\n    {\\n        $validated = $request->validate([\\n            'name' => 'required|string|max:255',\\n            'description' => 'nullable|string',\\n            'card_count' => 'required|integer|min:0',\\n        ]);\\n\\n        $game->update($validated);\\n\\n        return redirect()->route('games.index')\\n            ->with('success', 'Jeu mis à jour avec succès !');\\n    }\\n\\n    public function destroy(Game $game)\\n    {\\n        $game->delete();\\n\\n        return redirect()->route('games.index')\\n            ->with('success', 'Jeu supprimé avec succès !');\\n    }\\n}\\n"
    },
    {
      "type": "search_replace",
      "path": "routes/web.php",
      "search": "Route::get('/', function () {\\n    // Try views created by steps first\\n    if (view()->exists('home')) {\\n        return view('home');\\n    } elseif (view()->exists('index')) {\\n        return view('index');\\n    } elseif (view()->exists('welcome')) {\\n        return view('welcome');\\n    }\\n    return response()->view('welcome', [], 200);\\n});",
      "replace": "Route::get('/', function () {\\n    return redirect()->route('games.index');\\n});\\n\\nRoute::resource('games', App\\\\Http\\\\Controllers\\\\GameController::class);"
    },
    {
      "type": "create",
      "path": "resources/views/layouts/app.blade.php",
      "content": "[CONTENU DU LAYOUT COMPLET AVEC TAILWIND]"
    },
    {
      "type": "create",
      "path": "resources/views/games/index.blade.php",
      "content": "[VUE INDEX COMPLÈTE]"
    },
    {
      "type": "create",
      "path": "resources/views/games/create.blade.php",
      "content": "[VUE CREATE COMPLÈTE]"
    },
    {
      "type": "create",
      "path": "resources/views/games/edit.blade.php",
      "content": "[VUE EDIT COMPLÈTE]"
    },
    {
      "type": "create",
      "path": "resources/views/games/show.blade.php",
      "content": "[VUE SHOW COMPLÈTE]"
    }
  ]
}

═══════════════════════════════════════════════════════════════════
💡 NOTES IMPORTANTES
═══════════════════════════════════════════════════════════════════

• Utilisez les templates fournis dans les messages précédents
• Adaptez les noms de champs selon le contexte (name, description, etc.)
• Les vues doivent être belles (Tailwind) et fonctionnelles dès génération
• Pensez à la pagination, validation, flash messages
• Le layout doit être responsive et moderne

🎯 OBJECTIF : Application COMPLÈTE et FONCTIONNELLE dès la première génération !
"""
