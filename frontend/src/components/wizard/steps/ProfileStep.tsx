import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { RadioGroup, RadioGroupItem } from '@/components/ui/radio-group';
import { useSetupWizard } from '@/hooks/use-setup-wizard';
import { motion } from 'framer-motion';
import { ArrowLeft, ArrowRight, Mail, MessageSquare, Phone } from 'lucide-react';

const cities = [
  'Lahore',
  'Karachi',
  'Islamabad',
  'Multan',
  'Peshawar',
  'Faisalabad',
  'Rawalpindi',
  'Quetta',
  'Hyderabad',
  'Gujranwala',
];

const ProfileStep = () => {
  const { nextStep, prevStep, data, updateData } = useSetupWizard();

  const isValid = data.firstName.trim() && data.city;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      className="space-y-6"
    >
      <div className="text-center space-y-2">
        <h2 className="text-xl font-bold">Let's personalize your experience</h2>
        <p className="text-sm text-muted-foreground">
          Tell us a bit about yourself so we can tailor the app for you.
        </p>
      </div>

      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <Label htmlFor="firstName">First Name *</Label>
            <Input
              id="firstName"
              placeholder="Ahmed"
              value={data.firstName}
              onChange={(e) => updateData({ firstName: e.target.value })}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="lastName">Last Name</Label>
            <Input
              id="lastName"
              placeholder="Khan"
              value={data.lastName}
              onChange={(e) => updateData({ lastName: e.target.value })}
            />
          </div>
        </div>

        <div className="space-y-2">
          <Label htmlFor="city">City *</Label>
          <Select value={data.city} onValueChange={(value) => updateData({ city: value })}>
            <SelectTrigger>
              <SelectValue placeholder="Select your city" />
            </SelectTrigger>
            <SelectContent>
              {cities.map((city) => (
                <SelectItem key={city} value={city}>
                  {city}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-3">
          <Label>How would you like us to contact you?</Label>
          <RadioGroup
            value={data.contactPreference}
            onValueChange={(value: 'email' | 'sms' | 'whatsapp') => updateData({ contactPreference: value })}
            className="grid grid-cols-3 gap-3"
          >
            <Label
              htmlFor="email"
              className="flex flex-col items-center gap-2 p-3 rounded-lg border cursor-pointer hover:bg-muted/50 [&:has(:checked)]:border-primary [&:has(:checked)]:bg-primary/5"
            >
              <RadioGroupItem value="email" id="email" className="sr-only" />
              <Mail className="h-5 w-5" />
              <span className="text-xs">Email</span>
            </Label>
            <Label
              htmlFor="sms"
              className="flex flex-col items-center gap-2 p-3 rounded-lg border cursor-pointer hover:bg-muted/50 [&:has(:checked)]:border-primary [&:has(:checked)]:bg-primary/5"
            >
              <RadioGroupItem value="sms" id="sms" className="sr-only" />
              <Phone className="h-5 w-5" />
              <span className="text-xs">SMS</span>
            </Label>
            <Label
              htmlFor="whatsapp"
              className="flex flex-col items-center gap-2 p-3 rounded-lg border cursor-pointer hover:bg-muted/50 [&:has(:checked)]:border-primary [&:has(:checked)]:bg-primary/5"
            >
              <RadioGroupItem value="whatsapp" id="whatsapp" className="sr-only" />
              <MessageSquare className="h-5 w-5" />
              <span className="text-xs">WhatsApp</span>
            </Label>
          </RadioGroup>
        </div>
      </div>

      <div className="flex justify-between pt-4">
        <Button variant="outline" onClick={prevStep}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back
        </Button>
        <Button onClick={nextStep} disabled={!isValid}>
          Continue
          <ArrowRight className="h-4 w-4 ml-2" />
        </Button>
      </div>
    </motion.div>
  );
};

export default ProfileStep;
