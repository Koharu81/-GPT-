import { Toaster } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import NotFound from "@/pages/NotFound";
import { Route, Switch } from "wouter";
import ErrorBoundary from "./components/ErrorBoundary";
import { ThemeProvider } from "./contexts/ThemeContext";
import Home from "./pages/Home";
import StudioShell from "./pages/StudioShell";
import StudioChat from "./pages/StudioChat";
import TrainingData from "./pages/TrainingData";
import Training from "./pages/Training";
import ApiKeys from "./pages/ApiKeys";
import Admin from "./pages/Admin";
import ConversationHistory from "./pages/ConversationHistory";
import ModelVersions from "./pages/ModelVersions";

const studioPage = (Page: React.ComponentType) => () => <StudioShell><Page /></StudioShell>;

function Router() {
  // make sure to consider if you need authentication for certain routes
  return (
    <Switch>
      <Route path={"/"} component={Home} />
      <Route path={"/studio/chat"} component={studioPage(StudioChat)} />
      <Route path={"/studio/history"} component={studioPage(ConversationHistory)} />
      <Route path={"/studio/data"} component={studioPage(TrainingData)} />
      <Route path={"/studio/training"} component={studioPage(Training)} />
      <Route path={"/studio/models"} component={studioPage(ModelVersions)} />
      <Route path={"/studio/keys"} component={studioPage(ApiKeys)} />
      <Route path={"/studio/admin"} component={studioPage(Admin)} />
      <Route path={"/404"} component={NotFound} />
      {/* Final fallback route */}
      <Route component={NotFound} />
    </Switch>
  );
}

// NOTE: About Theme
// - First choose a default theme according to your design style (dark or light bg), than change color palette in index.css
//   to keep consistent foreground/background color across components
// - If you want to make theme switchable, pass `switchable` ThemeProvider and use `useTheme` hook

function App() {
  return (
    <ErrorBoundary>
      <ThemeProvider
        defaultTheme="dark"
        // switchable
      >
        <TooltipProvider>
          <Toaster />
          <Router />
        </TooltipProvider>
      </ThemeProvider>
    </ErrorBoundary>
  );
}

export default App;
