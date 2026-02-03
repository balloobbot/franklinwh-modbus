
---

## `screenshots/dashboard-mockup.html`

Interactive HTML mockup you can open in browser:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>FranklinWH Dashboard Mockup</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
        * { font-family: 'Inter', sans-serif; }
        .mockup-shadow { box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.25); }
        .glass { background: rgba(255,255,255,0.95); backdrop-filter: blur(10px); }
        .dark .glass { background: rgba(31,41,55,0.95); }
        
        /* Animated elements */
        @keyframes pulse-green {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.6; }
        }
        .animate-pulse-green { animation: pulse-green 2s ease-in-out infinite; }
        
        @keyframes flow-down {
            0% { transform: translateY(-5px); opacity: 0.5; }
            50% { transform: translateY(0); opacity: 1; }
            100% { transform: translateY(5px); opacity: 0.5; }
        }
        .flow-down { animation: flow-down 1.5s ease-in-out infinite; }
    </style>
    <script>
        tailwind.config = { darkMode: 'class' }
    </script>
</head>
<body class="bg-gray-100 dark:bg-gray-900 p-8">
    
    <div class="max-w-6xl mx-auto">
        <h1 class="text-3xl font-bold mb-2 text-gray-800 dark:text-white">FranklinWH Dashboard Mockup</h1>
        <p class="text-gray-600 dark:text-gray-400 mb-8">Interactive preview of the web interface. Toggle dark mode: 
            <button onclick="document.documentElement.classList.toggle('dark')" class="px-3 py-1 bg-blue-500 text-white rounded">Toggle Theme</button>
        </p>
        
        <!-- Browser Chrome -->
        <div class="bg-gray-800 rounded-t-lg p-3 flex items-center gap-2">
            <div class="flex gap-1.5">
                <div class="w-3 h-3 rounded-full bg-red-500"></div>
                <div class="w-3 h-3 rounded-full bg-yellow-500"></div>
                <div class="w-3 h-3 rounded-full bg-green-500"></div>
            </div>
            <div class="flex-1 bg-gray-700 rounded px-3 py-1 text-sm text-gray-400 text-center">
                http://192.168.0.100:8080
            </div>
        </div>
        
        <!-- App Container -->
        <div class="mockup-shadow bg-white dark:bg-gray-900 rounded-b-lg overflow-hidden border dark:border-gray-700" style="height: 700px;">
            
            <!-- Header -->
            <div class="h-14 bg-white dark:bg-gray-800 border-b dark:border-gray-700 flex items-center justify-between px-4">
                <div class="flex items-center gap-3">
                    <button class="w-9 h-9 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center justify-center">
                        <i class="fas fa-bars text-gray-600 dark:text-gray-400"></i>
                    </button>
                    <div class="flex items-center gap-2">
                        <div class="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-green-500 flex items-center justify-center text-white font-bold text-sm">F</div>
                        <span class="font-semibold text-gray-800 dark:text-white hidden sm:block">FranklinWH</span>
                    </div>
                </div>
                
                <div class="flex items-center gap-2">
                    <label class="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 cursor-pointer">
                        <div class="w-9 h-5 bg-blue-500 rounded-full relative">
                            <div class="absolute right-1 top-1 w-3 h-3 bg-white rounded-full"></div>
                        </div>
                        Auto
                    </label>
                    <span class="text-xs text-gray-400">Next: 12s</span>
                    
                    <button class="w-9 h-9 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center justify-center">
                        <i class="fas fa-sync-alt text-gray-600 dark:text-gray-400"></i>
                    </button>
                    <button class="w-9 h-9 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center justify-center">
                        <i class="fas fa-cog text-gray-600 dark:text-gray-400"></i>
                    </button>
                </div>
            </div>
            
            <div class="flex h-[calc(100%-3.5rem)]">
                <!-- Sidebar -->
                <div class="w-60 bg-white dark:bg-gray-800 border-r dark:border-gray-700 hidden md:block">
                    <nav class="p-3 space-y-1">
                        <a href="#" class="flex items-center gap-3 px-3 py-2.5 rounded-lg bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 font-medium">
                            <i class="fas fa-tachometer-alt w-5"></i>
                            Dashboard
                        </a>
                        <a href="#" class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700">
                            <i class="fas fa-sliders-h w-5"></i>
                            Control
                        </a>
                        <a href="#" class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700">
                            <i class="fas fa-file-alt w-5"></i>
                            Logs
                        </a>
                        <a href="#" class="flex items-center gap-3 px-3 py-2.5 rounded-lg text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700">
                            <i class="fas fa-microchip w-5"></i>
                            Raw Registers
                        </a>
                    </nav>
                    
                    <div class="absolute bottom-0 w-60 p-4 border-t dark:border-gray-700">
                        <div class="flex items-center gap-2 text-sm">
                            <div class="w-2 h-2 rounded-full bg-green-500 animate-pulse-green"></div>
                            <span class="text-gray-500">Connected</span>
                        </div>
                        <div class="text-xs text-gray-400 mt-1">Updated: 14:32:15</div>
                    </div>
                </div>
                
                <!-- Main Content -->
                <div class="flex-1 overflow-y-auto p-6 bg-gray-50 dark:bg-gray-900">
                    
                    <!-- Stats Cards -->
                    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
                        
                        <!-- SOC Card -->
                        <div class="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm hover:shadow-md transition-shadow">
                            <div class="flex justify-between items-start mb-3">
                                <div>
                                    <p class="text-sm text-gray-500 dark:text-gray-400">State of Charge</p>
                                    <p class="text-3xl font-bold text-gray-800 dark:text-white">86.0%</p>
                                </div>
                                <div class="w-12 h-12 rounded-xl bg-green-100 dark:bg-green-900/30 text-green-600 flex items-center justify-center">
                                    <i class="fas fa-battery-three-quarters text-xl"></i>
                                </div>
                            </div>
                            <div class="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                                <div class="h-full bg-gradient-to-r from-red-500 via-amber-500 to-green-500" style="width: 86%"></div>
                            </div>
                        </div>
                        
                        <!-- Power Card -->
                        <div class="bg-white dark:bg-gray-800 rounded-xl p-5 shadow-sm hover:shadow-md transition-shadow">
                            <div class="flex justify-between items-start">
                                <div>
                                    <p class="text-sm text-gray-500 dark:text-gray-400">Power</p>
                                    <p class="text-2xl font-bold text-red-500">-1,250W</p>
                                </div>
                                <div class="w-12 h-12 rounded-xl bg-blue-100 dark:bg-blue-900/30 text-blue-600 flex items-center justify-center">
                                    <i class="fas fa-bolt text-xl"></i>
                                </div>
                            </div>
                            <p class="text-sm text-red-500 mt-2 flex items-center gap-1">
                                <i class="fas fa-arrow-up flow-down"></i>
                                <span>Dis
