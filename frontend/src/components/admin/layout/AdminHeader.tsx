import { Link, useNavigate } from "react-router-dom";
import { useAdminAuth } from "@/contexts/AdminAuthContext";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import {
  LogOut,
  User,
  Settings,
  Bell,
  Home,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface AdminHeaderProps {
  breadcrumbs?: Array<{ label: string; href?: string }>;
}

export function AdminHeader({ breadcrumbs }: AdminHeaderProps) {
  const { adminUser, logout } = useAdminAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/admin/login");
  };

  const getInitials = () => {
    if (!adminUser) return "A";
    return `${adminUser.firstName[0]}${adminUser.lastName[0]}`.toUpperCase();
  };

  const getRoleLabel = () => {
    if (!adminUser) return "";
    return adminUser.role.replace("_", " ").replace(/\b\w/g, l => l.toUpperCase());
  };

  return (
    <header className="sticky top-0 z-10 flex h-14 items-center justify-between border-b bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/60 px-6">
      {/* Breadcrumbs */}
      <div className="flex items-center gap-2">
        {breadcrumbs && breadcrumbs.length > 0 ? (
          <nav className="flex items-center gap-2 text-sm">
            {breadcrumbs.map((crumb, index) => (
              <div key={index} className="flex items-center gap-2">
                {index > 0 && (
                  <span className="text-muted-foreground">/</span>
                )}
                {crumb.href ? (
                  <Link
                    to={crumb.href}
                    className="text-muted-foreground hover:text-foreground transition-colors"
                  >
                    {crumb.label}
                  </Link>
                ) : (
                  <span className="font-medium">{crumb.label}</span>
                )}
              </div>
            ))}
          </nav>
        ) : (
          <h2 className="text-lg font-semibold">Admin Portal</h2>
        )}
      </div>

      {/* Right side - Actions */}
      <div className="flex items-center gap-3">
        {/* Go to User Portal */}
        <Button variant="ghost" size="sm" asChild>
          <Link to="/">
            <Home className="h-4 w-4 mr-2" />
            User Portal
          </Link>
        </Button>

        {/* Notifications */}
        <Button variant="ghost" size="icon" className="relative">
          <Bell className="h-4 w-4" />
          <span className="absolute top-1 right-1 h-2 w-2 rounded-full bg-destructive" />
        </Button>

        {/* User Menu */}
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button variant="ghost" className="gap-2 pl-2 pr-3">
              <Avatar className="h-7 w-7">
                <AvatarFallback className="text-xs bg-primary text-primary-foreground">
                  {getInitials()}
                </AvatarFallback>
              </Avatar>
              <div className="flex flex-col items-start text-left">
                <span className="text-sm font-medium">
                  {adminUser?.firstName} {adminUser?.lastName}
                </span>
                <Badge variant="secondary" className="text-xs px-1.5 py-0">
                  {getRoleLabel()}
                </Badge>
              </div>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuLabel>
              <div className="flex flex-col">
                <span>{adminUser?.email}</span>
                <span className="text-xs text-muted-foreground font-normal mt-1">
                  {getRoleLabel()}
                </span>
              </div>
            </DropdownMenuLabel>
            <DropdownMenuSeparator />
            <DropdownMenuItem asChild>
              <Link to="/admin/profile" className="cursor-pointer">
                <User className="mr-2 h-4 w-4" />
                Profile
              </Link>
            </DropdownMenuItem>
            <DropdownMenuItem asChild>
              <Link to="/admin/settings" className="cursor-pointer">
                <Settings className="mr-2 h-4 w-4" />
                Settings
              </Link>
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={handleLogout} className="cursor-pointer text-destructive focus:text-destructive">
              <LogOut className="mr-2 h-4 w-4" />
              Logout
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
