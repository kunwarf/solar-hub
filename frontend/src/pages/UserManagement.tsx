import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useNavigate } from "react-router-dom";
import { AppLayout } from "@/components/layout/AppLayout";
import { AppHeader } from "@/components/layout/AppHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import {
  Users,
  UserPlus,
  Crown,
  Shield,
  Eye,
  Wrench,
  Mail,
  Clock,
  ChevronDown,
  ChevronUp,
  Trash2,
  Send,
  RefreshCw,
  X,
  History,
  Filter,
  ArrowLeft,
  Info,
  HardHat,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import { useUserRole, UserRole, roleDescriptions } from "@/contexts/UserRoleContext";
import { formatDistanceToNow, format } from "date-fns";

const roleIcons: Record<UserRole, React.ElementType> = {
  owner: Crown,
  admin: Shield,
  viewer: Eye,
  installer: Wrench,
};

const roleColors: Record<UserRole, string> = {
  owner: "bg-amber-500/20 text-amber-600 border-amber-500/30",
  admin: "bg-primary/20 text-primary border-primary/30",
  viewer: "bg-muted text-muted-foreground border-border",
  installer: "bg-orange-500/20 text-orange-600 border-orange-500/30",
};

const UserManagementPage = () => {
  const navigate = useNavigate();
  const {
    currentUser,
    users,
    invitations,
    activityLog,
    hasPermission,
    isInstaller,
    updateUserRole,
    removeUser,
    inviteUser,
    cancelInvitation,
    resendInvitation,
  } = useUserRole();

  const [isInviteDialogOpen, setIsInviteDialogOpen] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<UserRole>("viewer");
  const [inviteMessage, setInviteMessage] = useState("");
  const [inviteDuration, setInviteDuration] = useState(7);
  const [isActivityLogOpen, setIsActivityLogOpen] = useState(false);
  const [activityFilter, setActivityFilter] = useState<string>("all");

  const canManageUsers = hasPermission("manage_users");

  const handleInviteUser = () => {
    if (!inviteEmail.trim()) {
      toast.error("Please enter an email address");
      return;
    }
    
    inviteUser(
      inviteEmail,
      inviteRole,
      inviteMessage || undefined,
      inviteRole === "installer" ? inviteDuration : undefined
    );
    
    toast.success(`Invitation sent to ${inviteEmail}`);
    setIsInviteDialogOpen(false);
    setInviteEmail("");
    setInviteRole("viewer");
    setInviteMessage("");
    setInviteDuration(7);
  };

  const handleRoleChange = (userId: string, newRole: UserRole) => {
    const user = users.find(u => u.id === userId);
    if (user?.role === "owner") {
      toast.error("Cannot change Owner's role");
      return;
    }
    updateUserRole(userId, newRole);
    toast.success(`Role updated to ${newRole}`);
  };

  const handleRemoveUser = (userId: string) => {
    removeUser(userId);
    toast.success("User removed successfully");
  };

  const handleResendInvitation = (invitationId: string) => {
    resendInvitation(invitationId);
    toast.success("Invitation resent");
  };

  const handleCancelInvitation = (invitationId: string) => {
    cancelInvitation(invitationId);
    toast.success("Invitation cancelled");
  };

  const filteredActivityLog = activityFilter === "all"
    ? activityLog
    : activityLog.filter(log => log.userId === activityFilter);

  const getInitials = (name: string) => {
    return name.split(" ").map(n => n[0]).join("").toUpperCase().slice(0, 2);
  };

  if (!canManageUsers) {
    return (
      <AppLayout>
        <AppHeader title="User Management" subtitle="Access restricted" />
        <div className="p-6 flex flex-col items-center justify-center min-h-[400px]">
          <Shield className="w-16 h-16 text-muted-foreground mb-4" />
          <h2 className="text-xl font-semibold text-foreground mb-2">Access Denied</h2>
          <p className="text-muted-foreground text-center max-w-md">
            You don't have permission to manage users. Contact your system administrator for access.
          </p>
          <Button variant="outline" className="mt-6" onClick={() => navigate("/settings")}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Settings
          </Button>
        </div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      {/* Installer Banner */}
      {isInstaller && (
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-orange-500/20 border-b border-orange-500/30 px-6 py-3"
        >
          <div className="flex items-center gap-3">
            <HardHat className="w-5 h-5 text-orange-600" />
            <span className="font-medium text-orange-600">Commissioning Mode</span>
            <span className="text-sm text-orange-600/80">
              Temporary installer access - expires {format(new Date(currentUser.installerExpiresAt || new Date()), "PPP")}
            </span>
          </div>
        </motion.div>
      )}

      <AppHeader 
        title="User Management" 
        subtitle="Manage team access and permissions"
      />
      
      <div className="p-6 space-y-6">
        {/* Current User Card */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="glass-card p-6"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <Avatar className="w-16 h-16">
                <AvatarFallback className="bg-primary/20 text-primary text-lg">
                  {getInitials(currentUser.name)}
                </AvatarFallback>
              </Avatar>
              <div>
                <h2 className="text-xl font-semibold text-foreground">{currentUser.name}</h2>
                <p className="text-sm text-muted-foreground">{currentUser.email}</p>
              </div>
            </div>
            
            <TooltipProvider>
              <Tooltip>
                <TooltipTrigger asChild>
                  <div className={cn(
                    "flex items-center gap-2 px-4 py-2 rounded-lg border",
                    roleColors[currentUser.role]
                  )}>
                    {(() => {
                      const RoleIcon = roleIcons[currentUser.role];
                      return <RoleIcon className="w-5 h-5" />;
                    })()}
                    <span className="font-medium capitalize">{currentUser.role}</span>
                    <Info className="w-4 h-4 opacity-60" />
                  </div>
                </TooltipTrigger>
                <TooltipContent side="left" className="max-w-xs">
                  <p>{roleDescriptions[currentUser.role]}</p>
                </TooltipContent>
              </Tooltip>
            </TooltipProvider>
          </div>
        </motion.div>

        {/* Team Members */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="glass-card p-6"
        >
          <div className="flex items-center justify-between mb-6">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center">
                <Users className="w-5 h-5 text-primary" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-foreground">Team Members</h3>
                <p className="text-sm text-muted-foreground">{users.length} members</p>
              </div>
            </div>
            
            <Dialog open={isInviteDialogOpen} onOpenChange={setIsInviteDialogOpen}>
              <DialogTrigger asChild>
                <Button className="gap-2">
                  <UserPlus className="w-4 h-4" />
                  Invite User
                </Button>
              </DialogTrigger>
              <DialogContent className="sm:max-w-md">
                <DialogHeader>
                  <DialogTitle>Invite Team Member</DialogTitle>
                  <DialogDescription>
                    Send an invitation to join your solar monitoring system
                  </DialogDescription>
                </DialogHeader>
                
                <div className="space-y-4 py-4">
                  <div className="space-y-2">
                    <Label htmlFor="invite-email">Email Address</Label>
                    <Input
                      id="invite-email"
                      type="email"
                      placeholder="user@example.com"
                      value={inviteEmail}
                      onChange={(e) => setInviteEmail(e.target.value)}
                    />
                  </div>
                  
                  <div className="space-y-2">
                    <Label>Role</Label>
                    <Select value={inviteRole} onValueChange={(v) => setInviteRole(v as UserRole)}>
                      <SelectTrigger>
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="admin">
                          <div className="flex items-center gap-2">
                            <Shield className="w-4 h-4" />
                            Admin
                          </div>
                        </SelectItem>
                        <SelectItem value="viewer">
                          <div className="flex items-center gap-2">
                            <Eye className="w-4 h-4" />
                            Viewer
                          </div>
                        </SelectItem>
                        <SelectItem value="installer">
                          <div className="flex items-center gap-2">
                            <Wrench className="w-4 h-4" />
                            Installer
                          </div>
                        </SelectItem>
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-muted-foreground">
                      {roleDescriptions[inviteRole]}
                    </p>
                  </div>
                  
                  {inviteRole === "installer" && (
                    <div className="space-y-2">
                      <Label>Access Duration</Label>
                      <Select value={inviteDuration.toString()} onValueChange={(v) => setInviteDuration(parseInt(v))}>
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="1">1 Day</SelectItem>
                          <SelectItem value="3">3 Days</SelectItem>
                          <SelectItem value="7">7 Days</SelectItem>
                          <SelectItem value="30">30 Days</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  )}
                  
                  <div className="space-y-2">
                    <Label htmlFor="invite-message">Message (Optional)</Label>
                    <Textarea
                      id="invite-message"
                      placeholder="Add a personal message..."
                      value={inviteMessage}
                      onChange={(e) => setInviteMessage(e.target.value)}
                      rows={3}
                    />
                  </div>
                </div>
                
                <DialogFooter>
                  <Button variant="outline" onClick={() => setIsInviteDialogOpen(false)}>
                    Cancel
                  </Button>
                  <Button onClick={handleInviteUser} className="gap-2">
                    <Send className="w-4 h-4" />
                    Send Invite
                  </Button>
                </DialogFooter>
              </DialogContent>
            </Dialog>
          </div>

          <div className="space-y-3">
            {users.filter(u => u.id !== currentUser.id).map((user) => {
              const RoleIcon = roleIcons[user.role];
              const isOwner = user.role === "owner";
              
              return (
                <div
                  key={user.id}
                  className="flex items-center justify-between p-4 rounded-lg bg-secondary/30 hover:bg-secondary/50 transition-colors"
                >
                  <div className="flex items-center gap-4">
                    <Avatar>
                      <AvatarFallback className="bg-primary/10 text-primary">
                        {getInitials(user.name)}
                      </AvatarFallback>
                    </Avatar>
                    <div>
                      <div className="flex items-center gap-2">
                        <p className="font-medium text-foreground">{user.name}</p>
                        <Badge variant="outline" className={cn("text-[10px]", roleColors[user.role])}>
                          <RoleIcon className="w-3 h-3 mr-1" />
                          {user.role}
                        </Badge>
                        {user.role === "installer" && user.installerExpiresAt && (
                          <Badge variant="outline" className="text-[10px] bg-orange-500/10 text-orange-600">
                            Expires {formatDistanceToNow(new Date(user.installerExpiresAt), { addSuffix: true })}
                          </Badge>
                        )}
                      </div>
                      <p className="text-sm text-muted-foreground">{user.email}</p>
                      <p className="text-xs text-muted-foreground">
                        Last active {user.lastActive ? formatDistanceToNow(new Date(user.lastActive), { addSuffix: true }) : "Never"}
                      </p>
                    </div>
                  </div>
                  
                  <div className="flex items-center gap-2">
                    {!isOwner && currentUser.role === "owner" && (
                      <>
                        <Select
                          value={user.role}
                          onValueChange={(v) => handleRoleChange(user.id, v as UserRole)}
                        >
                          <SelectTrigger className="w-[120px]">
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="admin">Admin</SelectItem>
                            <SelectItem value="viewer">Viewer</SelectItem>
                            <SelectItem value="installer">Installer</SelectItem>
                          </SelectContent>
                        </Select>
                        
                        <AlertDialog>
                          <AlertDialogTrigger asChild>
                            <Button variant="ghost" size="icon" className="text-destructive hover:text-destructive">
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </AlertDialogTrigger>
                          <AlertDialogContent>
                            <AlertDialogHeader>
                              <AlertDialogTitle>Remove User</AlertDialogTitle>
                              <AlertDialogDescription>
                                Are you sure you want to remove {user.name}? They will lose access to this system immediately.
                              </AlertDialogDescription>
                            </AlertDialogHeader>
                            <AlertDialogFooter>
                              <AlertDialogCancel>Cancel</AlertDialogCancel>
                              <AlertDialogAction
                                onClick={() => handleRemoveUser(user.id)}
                                className="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                              >
                                Remove
                              </AlertDialogAction>
                            </AlertDialogFooter>
                          </AlertDialogContent>
                        </AlertDialog>
                      </>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </motion.div>

        {/* Pending Invitations */}
        {invitations.length > 0 && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="glass-card p-6"
          >
            <div className="flex items-center gap-3 mb-6">
              <div className="w-10 h-10 rounded-lg bg-warning/20 flex items-center justify-center">
                <Mail className="w-5 h-5 text-warning" />
              </div>
              <div>
                <h3 className="text-lg font-semibold text-foreground">Pending Invitations</h3>
                <p className="text-sm text-muted-foreground">{invitations.length} pending</p>
              </div>
            </div>

            <div className="space-y-3">
              {invitations.map((invitation) => {
                const RoleIcon = roleIcons[invitation.role];
                const isExpired = new Date(invitation.expiresAt) < new Date();
                
                return (
                  <div
                    key={invitation.id}
                    className={cn(
                      "flex items-center justify-between p-4 rounded-lg",
                      isExpired ? "bg-destructive/10 border border-destructive/20" : "bg-secondary/30"
                    )}
                  >
                    <div className="flex items-center gap-4">
                      <div className={cn(
                        "w-10 h-10 rounded-full flex items-center justify-center",
                        isExpired ? "bg-destructive/20" : "bg-primary/10"
                      )}>
                        <Mail className={cn("w-5 h-5", isExpired ? "text-destructive" : "text-primary")} />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <p className="font-medium text-foreground">{invitation.email}</p>
                          <Badge variant="outline" className={cn("text-[10px]", roleColors[invitation.role])}>
                            <RoleIcon className="w-3 h-3 mr-1" />
                            {invitation.role}
                          </Badge>
                          {isExpired && (
                            <Badge variant="destructive" className="text-[10px]">Expired</Badge>
                          )}
                        </div>
                        <div className="flex items-center gap-2 text-xs text-muted-foreground">
                          <span>Sent {formatDistanceToNow(new Date(invitation.sentAt), { addSuffix: true })}</span>
                          {!isExpired && (
                            <>
                              <span>•</span>
                              <span>Expires {formatDistanceToNow(new Date(invitation.expiresAt), { addSuffix: true })}</span>
                            </>
                          )}
                        </div>
                        {invitation.message && (
                          <p className="text-xs text-muted-foreground mt-1 italic">"{invitation.message}"</p>
                        )}
                      </div>
                    </div>
                    
                    <div className="flex items-center gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleResendInvitation(invitation.id)}
                        className="gap-1"
                      >
                        <RefreshCw className="w-4 h-4" />
                        Resend
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleCancelInvitation(invitation.id)}
                        className="text-destructive hover:text-destructive gap-1"
                      >
                        <X className="w-4 h-4" />
                        Cancel
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          </motion.div>
        )}

        {/* Activity Log */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
        >
          <Collapsible open={isActivityLogOpen} onOpenChange={setIsActivityLogOpen}>
            <div className="glass-card">
              <CollapsibleTrigger className="w-full p-6 flex items-center justify-between hover:bg-accent/30 transition-colors rounded-t-lg">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-primary/20 flex items-center justify-center">
                    <History className="w-5 h-5 text-primary" />
                  </div>
                  <div className="text-left">
                    <h3 className="text-lg font-semibold text-foreground">Activity Log</h3>
                    <p className="text-sm text-muted-foreground">Track user actions and changes</p>
                  </div>
                </div>
                {isActivityLogOpen ? (
                  <ChevronUp className="w-5 h-5 text-muted-foreground" />
                ) : (
                  <ChevronDown className="w-5 h-5 text-muted-foreground" />
                )}
              </CollapsibleTrigger>
              
              <CollapsibleContent>
                <div className="px-6 pb-6 space-y-4">
                  {/* Filter */}
                  <div className="flex items-center gap-3">
                    <Filter className="w-4 h-4 text-muted-foreground" />
                    <Select value={activityFilter} onValueChange={setActivityFilter}>
                      <SelectTrigger className="w-[200px]">
                        <SelectValue placeholder="Filter by user" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All Users</SelectItem>
                        {users.map((user) => (
                          <SelectItem key={user.id} value={user.id}>
                            {user.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  
                  {/* Log entries */}
                  <div className="space-y-2">
                    {filteredActivityLog.map((log) => (
                      <div
                        key={log.id}
                        className="flex items-start gap-3 p-3 rounded-lg bg-secondary/30"
                      >
                        <Avatar className="w-8 h-8">
                          <AvatarFallback className="bg-primary/10 text-primary text-xs">
                            {getInitials(log.userName)}
                          </AvatarFallback>
                        </Avatar>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className="font-medium text-sm text-foreground">{log.userName}</span>
                            <span className="text-sm text-muted-foreground">{log.action}</span>
                          </div>
                          <p className="text-xs text-muted-foreground">{log.details}</p>
                          <p className="text-xs text-muted-foreground font-mono mt-1">
                            {format(new Date(log.timestamp), "PPp")}
                          </p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </CollapsibleContent>
            </div>
          </Collapsible>
        </motion.div>

        {/* Back Button */}
        <div className="flex justify-start">
          <Button variant="outline" onClick={() => navigate("/settings")} className="gap-2">
            <ArrowLeft className="w-4 h-4" />
            Back to Settings
          </Button>
        </div>
      </div>
    </AppLayout>
  );
};

export default UserManagementPage;
